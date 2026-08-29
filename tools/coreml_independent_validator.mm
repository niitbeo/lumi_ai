#import <CoreML/CoreML.h>
#import <Foundation/Foundation.h>

#include <algorithm>
#include <filesystem>
#include <string>
#include <vector>

namespace fs = std::filesystem;

int main(int argc, char** argv) {
  @autoreleasepool {
    if (argc != 2) {
      std::fprintf(stderr, "usage: %s <decrypted_coreml_root>\n", argv[0]);
      return 2;
    }
    std::vector<fs::path> models;
    for (const auto& entry : fs::recursive_directory_iterator(argv[1])) {
      if (entry.is_regular_file() && entry.path().extension() == ".mlmodel") {
        models.push_back(entry.path());
      }
    }
    std::sort(models.begin(), models.end());

    std::size_t asset_count = 0;
    std::size_t load_count = 0;
    for (std::size_t index = 0; index < models.size(); ++index) {
      @autoreleasepool {
        NSString* path = [NSString stringWithUTF8String:models[index].c_str()];
        NSData* data = [NSData dataWithContentsOfFile:path];
        NSError* asset_error = nil;
        MLModelAsset* asset =
            [MLModelAsset modelAssetWithSpecificationData:data error:&asset_error];
        const bool asset_ok = asset != nil;
        asset_count += asset_ok ? 1 : 0;

        __block MLModel* loaded_model = nil;
        __block NSError* load_error = nil;
        if (asset_ok) {
          MLModelConfiguration* configuration = [[MLModelConfiguration alloc] init];
          configuration.computeUnits = MLComputeUnitsCPUOnly;
          dispatch_semaphore_t semaphore = dispatch_semaphore_create(0);
          [MLModel loadModelAsset:asset
                    configuration:configuration
                completionHandler:^(MLModel* model, NSError* error) {
                  loaded_model = model;
                  load_error = error;
                  dispatch_semaphore_signal(semaphore);
                }];
          dispatch_semaphore_wait(semaphore, DISPATCH_TIME_FOREVER);
        }
        const bool load_ok = loaded_model != nil;
        load_count += load_ok ? 1 : 0;
        const char* error_text = "";
        if (!load_ok) {
          NSError* error = load_error ?: asset_error;
          error_text = error ? error.localizedDescription.UTF8String : "unknown";
        }
        std::printf("MODEL %zu/%zu asset=%d loaded=%d path=%s error=%s\n",
                    index + 1, models.size(), asset_ok ? 1 : 0,
                    load_ok ? 1 : 0, models[index].c_str(), error_text);
        std::fflush(stdout);
      }
    }
    std::printf("SUMMARY total=%zu asset=%zu loaded=%zu\n", models.size(),
                asset_count, load_count);
    return asset_count == models.size() && load_count == models.size() ? 0 : 1;
  }
}
