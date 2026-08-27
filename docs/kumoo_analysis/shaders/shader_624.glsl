varying highp vec2 textureCoordinate; uniform highp vec2 center; uniform highp float strength; uniform highp float radius; uniform highp vec2 sourceSize; uniform sampler2D inputOffsetTexture; uniform sampler2D currentOffsetTexture; uniform sampler2D maskTexture; uniform highp float penradius; uniform highp float kGaussianSigma; uniform highp float protectInverse; uniform sampler2D protectMask; 
#if defined FLOATTOBYTE
 uniform highp float floatFactor; 
#endif
 void main() { highp vec4 lastOffset = texture2D(currentOffsetTexture, textureCoordinate); highp vec4 solidOffset = vec4(0.0); highp vec2 offset = vec2(0.0); highp vec4 endcolor = texture2D(inputOffsetTexture, textureCoordinate); 
#if defined FLOATTOBYTE
 highp float invFloatFactor = 1.0 / floatFactor; offset.x = invFloatFactor * (lastOffset.r + lastOffset.g / 255.0 - solidOffset.r - solidOffset.g / 255.0); offset.y = invFloatFactor * (lastOffset.b + lastOffset.a / 255.0 - solidOffset.b - solidOffset.a / 255.0); 
#else
 offset.xy = lastOffset.xy; 
#endif
 highp float dist_x = (textureCoordinate.x) * sourceSize.x - center.x; highp float dist_y = (textureCoordinate.y) * sourceSize.y - center.y; highp float normalizedLd = float(dist_x * dist_x + dist_y * dist_y) / (radius * radius); vec2 pos; pos.x = textureCoordinate.x * sourceSize.x; pos.y = textureCoordinate.y * sourceSize.y; float d = exp(-kGaussianSigma * length(pos - center) / radius); float d2 = step(length(pos - center) - radius, 0.0); float dense_mask = d * d2; highp float intensity = strength * dense_mask; highp vec2 delta = -intensity * offset; highp float penmask = float((dist_x + 1.0) * (dist_x + 1.0) + (dist_y + 1.0) * (dist_y + 1.0)) / (penradius * penradius); delta *= 1.0 - smoothstep(0.0, 1.0, penmask); float maskAlpha = texture2D(protectMask, textureCoordinate + delta).r; maskAlpha = mix(maskAlpha, 1.0 - maskAlpha, protectInverse); delta *= maskAlpha; highp float maskTarget = texture2D(maskTexture, textureCoordinate).r; delta *= maskTarget; 
#if defined FLOATTOBYTE
 vec2 newoffset = vec2(0.0); newoffset.x = endcolor.r + endcolor.g / 255.0 + delta.x * floatFactor; newoffset.y = endcolor.b + endcolor.a / 255.0 + delta.y * floatFactor; float x_tmp = floor(newoffset.x * 255.0); float y_tmp = floor(newoffset.y * 255.0); endcolor.r = x_tmp / 255.0; endcolor.g = newoffset.x * 255.0 - x_tmp; endcolor.b = y_tmp / 255.0; endcolor.a = newoffset.y * 255.0 - y_tmp; 
#else
 endcolor.xy = endcolor.xy + delta; endcolor.z = 1.0 - smoothstep(0.0, 1.0, penmask); 
#endif
 gl_FragColor = endcolor; }