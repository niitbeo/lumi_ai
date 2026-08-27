varying highp vec2 textureCoordinate; uniform highp vec2 center; uniform highp vec2 move; uniform highp float strength; uniform highp float radius; uniform highp vec2 offsetSize; uniform highp vec2 sourceSize; uniform sampler2D inputOffsetTexture; uniform highp float kPowSigma; const float PI = 3.141592653589; 
#if defined FLOATTOBYTE
 uniform highp float floatFactor; 
#endif
 void main() { highp vec4 endcolor = texture2D(inputOffsetTexture, textureCoordinate); highp vec2 offset = vec2(0.0); 
#if defined FLOATTOBYTE
 highp float invFloatFactor = 1.0 / floatFactor; offset.x = invFloatFactor * (endcolor.r + endcolor.g / 255.0 - 0.498); offset.y = invFloatFactor * (endcolor.b + endcolor.a / 255.0 - 0.498); 
#else
 offset.xy = endcolor.xy; 
#endif
 highp int dist_x = int((textureCoordinate.x + offset.x) * offsetSize.x - center.x); highp int dist_y = int((textureCoordinate.y + offset.y) * offsetSize.y - center.y); highp float Ld = float(dist_x * dist_x + dist_y * dist_y); int length = int(radius); int length2 = int(Ld / radius); highp vec2 delta = vec2(0.0); if (length2 < length) { highp float weight = float(length2) / float(length); weight = pow((cos(sqrt(weight) * PI) + 1.0) * 0.5, kPowSigma); delta = (strength * weight) * move; delta.x /= sourceSize.x; delta.y /= sourceSize.y; 
#if defined FLOATTOBYTE
 vec4 addcolor = texture2D(inputOffsetTexture, textureCoordinate + delta); vec2 newoffset = vec2(0.0); newoffset.x = addcolor.r + addcolor.g / 255.0 + delta.x * floatFactor; newoffset.y = addcolor.b + addcolor.a / 255.0 + delta.y * floatFactor; float x_tmp = floor(newoffset.x * 255.0); float y_tmp = floor(newoffset.y * 255.0); endcolor.r = x_tmp / 255.0; endcolor.g = newoffset.x * 255.0 - x_tmp; endcolor.b = y_tmp / 255.0; endcolor.a = newoffset.y * 255.0 - y_tmp; 
#else
 endcolor.xy = delta + texture2D(inputOffsetTexture, textureCoordinate + delta).xy; 
#endif
 } gl_FragColor = endcolor; }