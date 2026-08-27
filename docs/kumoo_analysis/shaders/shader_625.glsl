varying highp vec2 textureCoordinate; uniform highp vec2 normal_center; uniform highp float strength; uniform highp float radius; uniform highp vec2 sourceSize; uniform sampler2D inputOffsetTexture; uniform sampler2D currentOffsetTexture; uniform float isSwell; uniform highp float kGaussianSigma; uniform highp float protectInverse; uniform sampler2D protectMask; 
#if defined FLOATTOBYTE
 uniform highp float floatFactor; 
#endif
 void main() { const float PI = 3.141592653589; float maskAlpha = 1.0; highp vec4 lastOffset = texture2D(currentOffsetTexture, textureCoordinate); highp vec2 offset = vec2(0.0); highp vec4 endcolor = texture2D(inputOffsetTexture, textureCoordinate); highp vec4 lastCenterOffset = texture2D(currentOffsetTexture, normal_center); highp vec2 centerOffset = vec2(0.0); 
#if defined FLOATTOBYTE
 highp float invFloatFactor = 1.0 / floatFactor; offset.x = invFloatFactor * (lastOffset.r + lastOffset.g / 255.0); offset.y = invFloatFactor * (lastOffset.b + lastOffset.a / 255.0); centerOffset.x = invFloatFactor * (lastCenterOffset.r + lastCenterOffset.g / 255.0); centerOffset.y = invFloatFactor * (lastCenterOffset.b + lastCenterOffset.a / 255.0); 
#else
 offset.xy = lastCenterOffset.xy; centerOffset.xy = lastCenterOffset.xy; 
#endif
 highp vec2 adjust_center = normal_center + centerOffset; highp float dist_x = (textureCoordinate.x + offset.x - adjust_center.x) * sourceSize.x; highp float dist_y = (textureCoordinate.y + offset.y - adjust_center.y) * sourceSize.y; highp float Ld = float(dist_x * dist_x + dist_y * dist_y); int length = int(radius); highp int length2 = int(Ld / radius); highp vec2 delta = vec2(0.0); highp float weight = 1.0; if (length2 < length) { delta = vec2(dist_x / sourceSize.x, dist_y / sourceSize.y); weight = float(length2) / float(length); weight = pow((cos(sqrt(weight) * PI) + 1.0) * 0.5, kGaussianSigma); weight *= strength * 0.1; } if (isSwell > 0.5) { delta *= -weight; } else { delta *= weight; } maskAlpha = texture2D(protectMask, textureCoordinate).a; maskAlpha = mix(maskAlpha, 1.0 - maskAlpha, protectInverse); delta *= maskAlpha; 
#if defined FLOATTOBYTE
 vec2 newoffset = vec2(0.0); newoffset.x = endcolor.r + endcolor.g / 255.0 + delta.x * floatFactor; newoffset.y = endcolor.b + endcolor.a / 255.0 + delta.y * floatFactor; float x_tmp = floor(newoffset.x * 255.0); float y_tmp = floor(newoffset.y * 255.0); endcolor.r = x_tmp / 255.0; endcolor.g = newoffset.x * 255.0 - x_tmp; endcolor.b = y_tmp / 255.0; endcolor.a = newoffset.y * 255.0 - y_tmp; 
#else
 endcolor.xy = endcolor.xy + delta; 
#endif
 gl_FragColor = endcolor; }