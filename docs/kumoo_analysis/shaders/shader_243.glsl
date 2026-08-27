varying highp vec2 textureCoordinate; uniform highp vec2 center; uniform highp float strength; uniform highp float radius; uniform highp vec2 sourceSize; uniform sampler2D inputOffsetTexture; uniform sampler2D currentOffsetTexture; uniform sampler2D maskTexture; uniform highp float kGaussianSigma; 
#if defined WITHPROTECT
 uniform highp float protectInverse; uniform sampler2D protectMask; 
#endif
 
#if defined FLOATTOBYTE
 uniform highp float floatFactor; 
#endif
 void main() { float maskAlpha = 1.0; 
#if defined WITHPROTECT
 maskAlpha = texture2D(protectMask, textureCoordinate).r; maskAlpha = mix(maskAlpha, 1.0 - maskAlpha, protectInverse); 
#endif
 highp vec4 lastOffset = texture2D(currentOffsetTexture, textureCoordinate); highp vec2 offset = vec2(0.0); highp vec4 endcolor = texture2D(inputOffsetTexture, textureCoordinate); 
#if defined FLOATTOBYTE
 highp float invFloatFactor = 1.0 / floatFactor; offset.x = invFloatFactor * (lastOffset.r + lastOffset.g / 255.0); offset.y = invFloatFactor * (lastOffset.b + lastOffset.a / 255.0); 
#else
 offset.xy = lastOffset.xy; 
#endif
 highp float min_x = (center.x - 5.0 * radius) / sourceSize.x; highp float max_x = (center.x + 5.0 * radius) / sourceSize.x; highp float min_y = (center.y - 5.0 * radius) / sourceSize.y; highp float max_y = (center.y + 5.0 * radius) / sourceSize.y; if (textureCoordinate.x < min_x || textureCoordinate.x > max_x || textureCoordinate.y < min_y || textureCoordinate.y > max_y) { gl_FragColor = endcolor; return; } highp float dist_x = (textureCoordinate.x + offset.x) * sourceSize.x - center.x; highp float dist_y = (textureCoordinate.y + offset.y) * sourceSize.y - center.y; highp float normalizedLd = float(dist_x * dist_x + dist_y * dist_y) / (0.25 * radius * radius); highp float intensity = exp(-normalizedLd / (2.0 * kGaussianSigma * kGaussianSigma)); intensity = min(strength * intensity, 1.0); highp vec2 delta = -intensity * offset; highp float dist_x0 = (textureCoordinate.x + offset.x + delta.x) * sourceSize.x - center.x; highp float dist_y0 = (textureCoordinate.y + offset.y + delta.y) * sourceSize.y - center.y; highp float normalizedLd0 = float(delta.x * delta.x + delta.y * delta.y) / (radius * radius); delta *= max(0.0, 1.0 - 4.0 * normalizedLd0); highp float maskTarget = texture2D(maskTexture, textureCoordinate + offset + delta).r; delta *= maskTarget; delta *= maskAlpha; 
#if defined FLOATTOBYTE
 vec2 newoffset = vec2(0.0); newoffset.x = endcolor.r + endcolor.g / 255.0 + delta.x * floatFactor; newoffset.y = endcolor.b + endcolor.a / 255.0 + delta.y * floatFactor; float x_tmp = floor(newoffset.x * 255.0); float y_tmp = floor(newoffset.y * 255.0); endcolor.r = x_tmp / 255.0; endcolor.g = newoffset.x * 255.0 - x_tmp; endcolor.b = y_tmp / 255.0; endcolor.a = newoffset.y * 255.0 - y_tmp; 
#else
 endcolor.xy = endcolor.xy + delta; 
#endif
 gl_FragColor = endcolor; }