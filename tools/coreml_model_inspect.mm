#import <CoreML/CoreML.h>
#import <Foundation/Foundation.h>

#include <cstdio>
#include <cstring>
#include <fstream>
#include <vector>

static const char* featureTypeName(MLFeatureType type) {
  switch (type) {
    case MLFeatureTypeInt64: return "int64";
    case MLFeatureTypeDouble: return "double";
    case MLFeatureTypeString: return "string";
    case MLFeatureTypeImage: return "image";
    case MLFeatureTypeMultiArray: return "multiarray";
    case MLFeatureTypeDictionary: return "dictionary";
    case MLFeatureTypeSequence: return "sequence";
    default: return "invalid";
  }
}

static void printFeatures(NSDictionary<NSString*, MLFeatureDescription*>* features) {
  for (NSString* name in features) {
    MLFeatureDescription* feature = features[name];
    std::printf("  %s type=%s", name.UTF8String,
                featureTypeName(feature.type));
    if (feature.type == MLFeatureTypeMultiArray) {
      MLMultiArrayConstraint* constraint = feature.multiArrayConstraint;
      std::printf(" shape=[");
      for (NSUInteger index = 0; index < constraint.shape.count; ++index) {
        std::printf("%s%s", index ? "," : "",
                    constraint.shape[index].stringValue.UTF8String);
      }
      std::printf("] dtype=%ld", (long)constraint.dataType);
    } else if (feature.type == MLFeatureTypeImage) {
      MLImageConstraint* constraint = feature.imageConstraint;
      std::printf(" width=%ld height=%ld pixelFormat=%u",
                  (long)constraint.pixelsWide, (long)constraint.pixelsHigh,
                  (unsigned)constraint.pixelFormatType);
    }
    std::printf(" optional=%d\n", feature.optional ? 1 : 0);
  }
}

int main(int argc, char** argv) {
  @autoreleasepool {
    if (argc != 2 && argc != 4) {
      std::fprintf(stderr,
                   "usage: %s <model.mlmodel> [input-f32.raw output-f32.raw]\n",
                   argv[0]);
      return 2;
    }
    NSString* path = [NSString stringWithUTF8String:argv[1]];
    NSData* data = [NSData dataWithContentsOfFile:path];
    NSError* assetError = nil;
    MLModelAsset* asset =
        [MLModelAsset modelAssetWithSpecificationData:data error:&assetError];
    if (!asset) {
      std::fprintf(stderr, "asset error: %s\n",
                   assetError.localizedDescription.UTF8String);
      return 3;
    }

    MLModelConfiguration* configuration = [[MLModelConfiguration alloc] init];
    configuration.computeUnits = MLComputeUnitsCPUOnly;
    __block MLModel* model = nil;
    __block NSError* loadError = nil;
    dispatch_semaphore_t semaphore = dispatch_semaphore_create(0);
    [MLModel loadModelAsset:asset
              configuration:configuration
          completionHandler:^(MLModel* loadedModel, NSError* error) {
            model = loadedModel;
            loadError = error;
            dispatch_semaphore_signal(semaphore);
          }];
    dispatch_semaphore_wait(semaphore, DISPATCH_TIME_FOREVER);
    if (!model) {
      std::fprintf(stderr, "load error: %s\n",
                   loadError.localizedDescription.UTF8String);
      return 4;
    }

    std::printf("MODEL %s\nINPUTS\n", argv[1]);
    printFeatures(model.modelDescription.inputDescriptionsByName);
    std::printf("OUTPUTS\n");
    printFeatures(model.modelDescription.outputDescriptionsByName);

    if (argc == 4) {
      NSString* inputName = model.modelDescription.inputDescriptionsByName.allKeys.firstObject;
      NSString* outputName = model.modelDescription.outputDescriptionsByName.allKeys.firstObject;
      MLFeatureDescription* inputDescription =
          model.modelDescription.inputDescriptionsByName[inputName];
      NSArray<NSNumber*>* shape = inputDescription.multiArrayConstraint.shape;
      NSUInteger count = 1;
      for (NSNumber* dimension in shape) count *= dimension.unsignedIntegerValue;

      std::vector<float> input(count);
      std::ifstream inputFile(argv[2], std::ios::binary);
      inputFile.read(reinterpret_cast<char*>(input.data()),
                     static_cast<std::streamsize>(count * sizeof(float)));
      if (!inputFile || inputFile.gcount() !=
                            static_cast<std::streamsize>(count * sizeof(float))) {
        std::fprintf(stderr, "input must contain %lu float32 values\n",
                     (unsigned long)count);
        return 5;
      }

      NSError* arrayError = nil;
      MLMultiArray* inputArray = [[MLMultiArray alloc]
          initWithShape:shape
               dataType:inputDescription.multiArrayConstraint.dataType
                  error:&arrayError];
      if (!inputArray) {
        std::fprintf(stderr, "array error: %s\n",
                     arrayError.localizedDescription.UTF8String);
        return 6;
      }
      std::memcpy(inputArray.dataPointer, input.data(), count * sizeof(float));
      MLFeatureValue* inputValue =
          [MLFeatureValue featureValueWithMultiArray:inputArray];
      NSError* providerError = nil;
      MLDictionaryFeatureProvider* provider = [[MLDictionaryFeatureProvider alloc]
          initWithDictionary:@{inputName : inputValue}
                       error:&providerError];
      NSError* predictionError = nil;
      id<MLFeatureProvider> prediction =
          [model predictionFromFeatures:provider error:&predictionError];
      if (!prediction) {
        std::fprintf(stderr, "prediction error: %s\n",
                     predictionError.localizedDescription.UTF8String);
        return 7;
      }
      MLMultiArray* outputArray =
          [prediction featureValueForName:outputName].multiArrayValue;
      std::ofstream outputFile(argv[3], std::ios::binary);
      outputFile.write(reinterpret_cast<const char*>(outputArray.dataPointer),
                       static_cast<std::streamsize>(outputArray.count * sizeof(float)));
      std::printf("PREDICTION output=%s count=%lu\n", outputName.UTF8String,
                  (unsigned long)outputArray.count);
    }
    return 0;
  }
}
