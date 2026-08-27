varying vec2 textureCoordinate; uniform sampler2D offsetTexture; uniform sampler2D protectMask; uniform highp float protectInverse; 
#if defined FLOATTOBYTE
 uniform highp float floatFactor; 
#endif
 void main() { highp vec4 offsetValue = texture2D(offsetTexture, textureCoordinate); float maskAlpha = texture2D(protectMask, textureCoordinate).r; maskAlpha = mix(maskAlpha, 1.0 - maskAlpha, protectInverse); highp vec2 offset = vec2(0.0); 
#if defined FLOATTOBYTE
 highp float invFloatFactor = 1.0 / floatFactor; offset.x = invFloatFactor * (offsetValue.r + offsetValue.g / 255.0 - 0.498); offset.y = invFloatFactor * (offsetValue.b + offsetValue.a / 255.0 - 0.498); 
#else
 offset = offsetValue.xy; 
#endif
 highp vec2 finalOffset = offset * maskAlpha; vec4 endColor = vec4(0.0); 
#if defined FLOATTOBYTE
 finalOffset.xy = finalOffset.xy * floatFactor + vec2(0.498); float x_tmp = floor(finalOffset.x * 255.0); float y_tmp = floor(finalOffset.y * 255.0); endColor.r = x_tmp / 255.0; endColor.g = finalOffset.x * 255.0 - x_tmp; endColor.b = y_tmp / 255.0; endColor.a = finalOffset.y * 255.0 - y_tmp; 
#else
 endColor.xy = finalOffset.xy; 
#endif
 gl_FragColor = endColor; }