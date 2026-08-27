varying highp vec2 textureCoordinate; uniform highp vec2 center; uniform highp vec2 move; uniform highp float strength; uniform highp float radius; uniform highp vec2 sourceSize; uniform highp float penradius; uniform sampler2D inputOffsetTexture; uniform sampler2D maskTexture; uniform highp float kGaussianSigma; uniform highp float kBrushAlpha; uniform highp float protectInverse; uniform sampler2D protectMask; 
#if defined FLOATTOBYTE
 uniform highp float floatFactor; 
#endif
 void main() { highp vec4 endcolor = texture2D(inputOffsetTexture, textureCoordinate); highp vec2 offset = vec2(0.0); 
#if defined FLOATTOBYTE
 highp float invFloatFactor = 1.0 / floatFactor; offset.x = invFloatFactor * (endcolor.r + endcolor.g / 255.0 - 0.498); offset.y = invFloatFactor * (endcolor.b + endcolor.a / 255.0 - 0.498); 
#else
 offset.xy = endcolor.xy; 
#endif
 highp float min_x = (center.x - 5.0 * radius) / sourceSize.x; highp float max_x = (center.x + 5.0 * radius) / sourceSize.x; highp float min_y = (center.y - 5.0 * radius) / sourceSize.y; highp float max_y = (center.y + 5.0 * radius) / sourceSize.y; if (textureCoordinate.x < min_x || textureCoordinate.x > max_x || textureCoordinate.y < min_y || textureCoordinate.y > max_y) { gl_FragColor = endcolor; return; } highp float dist_x = (textureCoordinate.x + offset.x) * sourceSize.x - center.x; highp float dist_y = (textureCoordinate.y + offset.y) * sourceSize.y - center.y; highp float normalizedLd = float(dist_x * dist_x + dist_y * dist_y) / (radius * radius); highp float penmask = float((dist_x + 1e-3) * (dist_x + 1e-3) + (dist_y + 1e-3) * (dist_y + 1e-3)) / (penradius * penradius); highp vec2 pos; pos.x = textureCoordinate.x * sourceSize.x; pos.y = textureCoordinate.y * sourceSize.y; highp float d = clamp(length(pos - center) / radius, 0.0, 1.0); d = -kGaussianSigma * d; d = 1.0 + d + d * d * 0.5; highp float d2 = step(length(pos - center) - radius, 0.0); highp float dense_mask = d * d2; highp float intensity = clamp(0.1 * normalizedLd, 0.0, 1.0); intensity = 1.0 + intensity + intensity * intensity * 0.5; intensity = dense_mask / intensity; highp vec2 delta = strength * move; delta.x /= sourceSize.x; delta.y /= sourceSize.y; highp float maskTarget = texture2D(maskTexture, textureCoordinate + delta).r; delta *= clamp(0.85 + 0.15 * maskTarget, 0.0, 1.0); delta *= clamp(1.0 - smoothstep(0.0, 1.0, penmask), 0.0, 1.0); delta *= clamp(1.0 - kBrushAlpha * normalizedLd, 0.0, 1.0); highp float maskAlpha = texture2D(protectMask, textureCoordinate + delta).r; maskAlpha = mix(maskAlpha, 1.0 - maskAlpha, protectInverse); delta *= maskAlpha; delta *= intensity; 
#if defined FLOATTOBYTE
 highp vec2 newoffset = vec2(0.0); newoffset.x = endcolor.r + endcolor.g / 255.0 + delta.x * floatFactor; newoffset.y = endcolor.b + endcolor.a / 255.0 + delta.y * floatFactor; float x_tmp = floor(newoffset.x * 255.0); float y_tmp = floor(newoffset.y * 255.0); endcolor.r = x_tmp / 255.0; endcolor.g = newoffset.x * 255.0 - x_tmp; endcolor.b = y_tmp / 255.0; endcolor.a = newoffset.y * 255.0 - y_tmp; 
#else
 endcolor.xy = delta + offset; endcolor.z = 1.0 - smoothstep(0.0, 1.0, penmask); 
#endif
 gl_FragColor = endcolor; }