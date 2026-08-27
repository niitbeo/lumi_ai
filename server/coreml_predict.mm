#import <CoreML/CoreML.h>
#import <Foundation/Foundation.h>

#include <cstdio>
#include <cstring>
#include <fstream>
#include <vector>

int main(int argc, char** argv) {
  @autoreleasepool {
    if (argc != 4) {
      std::fprintf(stderr, "usage: %s <model.mlmodel> <input-f32.raw> <output-f32.raw>\n", argv[0]);
      return 2;
    }

    NSString* modelPath = [NSString stringWithUTF8String:argv[1]];
    NSData* specification = [NSData dataWithContentsOfFile:modelPath];
    NSError* error = nil;
    MLModelAsset* asset =
        [MLModelAsset modelAssetWithSpecificationData:specification error:&error];
    if (!asset) {
      std::fprintf(stderr, "model asset: %s\n", error.localizedDescription.UTF8String);
      return 3;
    }

    MLModelConfiguration* configuration = [[MLModelConfiguration alloc] init];
    configuration.computeUnits = MLComputeUnitsCPUOnly;
    __block MLModel* model = nil;
    __block NSError* loadError = nil;
    dispatch_semaphore_t semaphore = dispatch_semaphore_create(0);
    [MLModel loadModelAsset:asset
              configuration:configuration
          completionHandler:^(MLModel* loadedModel, NSError* modelError) {
            model = loadedModel;
            loadError = modelError;
            dispatch_semaphore_signal(semaphore);
          }];
    dispatch_semaphore_wait(semaphore, DISPATCH_TIME_FOREVER);
    if (!model) {
      std::fprintf(stderr, "model load: %s\n", loadError.localizedDescription.UTF8String);
      return 4;
    }

    NSString* inputName = model.modelDescription.inputDescriptionsByName.allKeys.firstObject;
    NSString* outputName = model.modelDescription.outputDescriptionsByName.allKeys.firstObject;
    MLFeatureDescription* inputDescription =
        model.modelDescription.inputDescriptionsByName[inputName];
    if (inputDescription.type != MLFeatureTypeMultiArray || !outputName) {
      std::fprintf(stderr, "runner requires one multi-array input and one output\n");
      return 5;
    }

    NSArray<NSNumber*>* shape = inputDescription.multiArrayConstraint.shape;
    NSUInteger inputCount = 1;
    for (NSNumber* dimension in shape) inputCount *= dimension.unsignedIntegerValue;

    std::vector<float> input(inputCount);
    std::ifstream inputFile(argv[2], std::ios::binary);
    inputFile.read(reinterpret_cast<char*>(input.data()),
                   static_cast<std::streamsize>(inputCount * sizeof(float)));
    if (!inputFile || inputFile.gcount() !=
                          static_cast<std::streamsize>(inputCount * sizeof(float))) {
      std::fprintf(stderr, "input must contain %lu float32 values\n",
                   static_cast<unsigned long>(inputCount));
      return 6;
    }

    MLMultiArray* inputArray = [[MLMultiArray alloc]
        initWithShape:shape
             dataType:inputDescription.multiArrayConstraint.dataType
                error:&error];
    if (!inputArray) {
      std::fprintf(stderr, "input array: %s\n", error.localizedDescription.UTF8String);
      return 7;
    }
    std::memcpy(inputArray.dataPointer, input.data(), inputCount * sizeof(float));

    MLDictionaryFeatureProvider* provider = [[MLDictionaryFeatureProvider alloc]
        initWithDictionary:@{
          inputName : [MLFeatureValue featureValueWithMultiArray:inputArray]
        }
                     error:&error];
    id<MLFeatureProvider> prediction =
        [model predictionFromFeatures:provider error:&error];
    if (!prediction) {
      std::fprintf(stderr, "prediction: %s\n", error.localizedDescription.UTF8String);
      return 8;
    }

    MLMultiArray* outputArray =
        [prediction featureValueForName:outputName].multiArrayValue;
    if (!outputArray || outputArray.dataType != MLMultiArrayDataTypeFloat32) {
      std::fprintf(stderr, "model output is not a float32 multi-array\n");
      return 9;
    }

    std::ofstream outputFile(argv[3], std::ios::binary);
    outputFile.write(reinterpret_cast<const char*>(outputArray.dataPointer),
                     static_cast<std::streamsize>(outputArray.count * sizeof(float)));
    if (!outputFile) {
      std::fprintf(stderr, "cannot write output\n");
      return 10;
    }
    return 0;
  }
}
