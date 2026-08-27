uniform sampler2D inputImageTexture; uniform sampler2D inputImageTexture2; uniform sampler2D inputImageTexture3; varying highp vec2 textureCoordinate; varying highp vec2 textureCoordinateCrop; uniform lowp float laughLineAlpha; uniform lowp float removePouchAlpha; uniform sampler2D laughLineMaskTexture; uniform sampler2D skinMaskTexture; uniform sampler2D nevusMaskTexture; uniform lowp float darkAlpha; 
#if defined WITH_JOWLBRIGHT
 uniform sampler2D archFillerMaskTexture; uniform lowp float jowlFillAlpha; uniform lowp vec3 fAverageFaceColor; uniform lowp vec2 center1; uniform lowp vec2 center2; uniform lowp vec2 attenuation; lowp float isLeft(vec2 v12, vec2 v13) { float crossProduct = v12.x * v13.y - v12.y * v13.x; return step(0.0, crossProduct); } 
#endif 
 void main() { lowp vec4 iColor = texture2D(inputImageTexture, textureCoordinate); lowp vec3 laughLineMask = texture2D(laughLineMaskTexture, textureCoordinate).rgb; lowp float skinMask = texture2D(skinMaskTexture, textureCoordinate).r; lowp vec3 color = iColor.rgb; if (laughLineMask.g > 0.0500) { color = iColor.rgb; } else { lowp vec3 lowColor = texture2D(inputImageTexture3, textureCoordinateCrop).rgb; lowp vec3 meanColor = texture2D(inputImageTexture2, textureCoordinateCrop).rgb; lowp vec3 highColor = color - lowColor; lowp float bright_alpha = max(removePouchAlpha * laughLineMask.r, laughLineAlpha * laughLineMask.b); 
#if defined WITH_JOWLBRIGHT
 lowp vec3 jowlFillColor = texture2D(archFillerMaskTexture, textureCoordinate).rgb; lowp float fIsLeft = isLeft(center2-center1, textureCoordinate.xy - center1); lowp float jowlBrightAlpha = jowlFillAlpha*mix(attenuation.y, attenuation.x, fIsLeft); bright_alpha = max(bright_alpha, jowlFillColor.b*jowlBrightAlpha); 
#endif 
 lowp vec3 imDiff = clamp((meanColor - lowColor) * 1.3 + 0.03 * meanColor, 0.0, 0.2); lowp vec3 threshold = mix(meanColor * 1.02, meanColor, darkAlpha); lowp vec3 tempColor = iColor.rgb - highColor; tempColor.r = max(threshold.r, tempColor.r); tempColor.g = max(threshold.g, tempColor.g); tempColor.b = max(threshold.b, tempColor.b); lowp vec3 newColorPouch = clamp(color + imDiff - highColor, vec3(0.0), tempColor) + highColor; 
#if defined SHADOW_BRIGHT_TAERI 
 lowp vec3 newColorLaughline = color + imDiff;; newColorLaughline.r = min(newColorLaughline.r, 1.0); newColorLaughline.g = min(newColorLaughline.g, 1.0); newColorLaughline.b = min(newColorLaughline.b, 1.0); lowp vec3 newColor = mix(newColorLaughline, newColorPouch, laughLineMask.r); 
#else 
 lowp vec3 newColor = newColorPouch; 
#endif 
 float nevusMaskColor = texture2D(nevusMaskTexture, textureCoordinate).r; color = mix(color, newColor, bright_alpha * skinMask * nevusMaskColor); 
#if defined WITH_JOWLBRIGHT
 color = mix(color-highColor, newColor - highColor, bright_alpha * skinMask * nevusMaskColor); color += highColor; 
#endif 
 } gl_FragColor = vec4(color, iColor.a); }