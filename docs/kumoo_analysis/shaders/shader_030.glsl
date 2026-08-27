
                uniform lowp sampler2D inputImageTexture;
                 uniform lowp sampler2D mt_tempData1;//sharpenBlurTexture
                 uniform lowp sampler2D mt_tempData2;//structureHistogramTexture
                 uniform float sharpenStrength;
                 uniform float structureStrength;
                 uniform vec2 structureCountTiles;
                 uniform vec3 structureHistogramTextureSize;
                 
                 varying   vec2  glv_TextureCoords;
                 varying   vec2  glv_TextureCoords1;
                 
                 const float kStructureLookupBlurFactor = 0.066667;
                 
                 void main() {
                     vec3 color = texture2D(inputImageTexture, glv_TextureCoords).rgb;
                     
                     // Perform sharpening.
                     float sharpenLumOrig = color.r * 0.3333 + color.g * 0.5 + color.b * 0.1667;
                     float sharpenDLum =
                     sharpenLumOrig - texture2D(mt_tempData1, glv_TextureCoords1).a;
                     color = clamp(color + sharpenDLum * sharpenStrength, 0.0, 1.0);
                     
                     // Apply structure. For the lsc histogram lookup we mix in the blurred
                     // luminance to reduce edge artifacts.
                     float structureLookupLum = clamp(sharpenLumOrig + clamp(-sharpenDLum,
                                                                             -kStructureLookupBlurFactor, kStructureLookupBlurFactor), 0.01, 1.0 - 0.01);
                     
                     // Structure sample positions. One histogram is 64 pixels wide.
                     vec2 tilePos = glv_TextureCoords1 * structureCountTiles;
                     vec2 low = floor(tilePos - 0.5);
                     vec2 high = low + 1.0;
                     low = max(low, 0.0);
                     high = min(high, structureCountTiles - 1.0);
                     
                     vec2 lookupX = (vec2(low.x, high.x) * 64.0 + 0.1 + structureLookupLum * 63.8)
                     / structureHistogramTextureSize.x;
                     vec2 lookupY = vec2(low.y, high.y)  / structureHistogramTextureSize.y +
                     structureHistogramTextureSize.z;
                     tilePos -= low + 0.5;
                     
                     vec2 resultYLowYHigh = mix(
                                                vec2(texture2D(mt_tempData2, vec2(lookupX.x, lookupY.y)).a,
                                                     texture2D(mt_tempData2, vec2(lookupX.x, lookupY.x)).a),
                                                vec2(texture2D(mt_tempData2, vec2(lookupX.y, lookupY.y)).a,
                                                     texture2D(mt_tempData2, vec2(lookupX.y, lookupY.x)).a),
                                                tilePos.x);
                     
                     float lsc_lum = mix(resultYLowYHigh.y, resultYLowYHigh.x, tilePos.y);
                     float lum_new1 = sharpenLumOrig + structureStrength *
                     (sharpenLumOrig * 1.4 - lsc_lum * 1.484 + 0.042) - 0.5;
                     float lo = sharpenLumOrig - 0.5;
                     float saerf = min((0.275 - lum_new1 * lum_new1) / (0.275 - lo * lo) *
                                       (1.0 + structureStrength / 5.0), 5.0);
                     
                     
                     gl_FragColor.rgb = lum_new1 + (color - sharpenLumOrig) * saerf + 0.5;
                     gl_FragColor.a = 1.0;
                 }
                
                