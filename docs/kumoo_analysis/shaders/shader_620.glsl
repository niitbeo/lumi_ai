uniform sampler2D inputImageTexture; uniform sampler2D localOffsetTexture; varying vec2 textureCoordinate; varying vec2 textureCoordinate2; uniform highp float scale_x; uniform highp float scale_y; uniform int isRemove; 
#if defined FLOATTOBYTE
 uniform highp float floatFactor; 
#endif
 void main() { highp vec4 inputcolor = texture2D(localOffsetTexture, textureCoordinate2); highp vec2 scaleoffset = vec2(0.0); 
#if defined FLOATTOBYTE
 highp float invFloatFactor = 1.0 / floatFactor; scaleoffset.x = invFloatFactor * (inputcolor.r + inputcolor.g / 255.0 - 0.498); scaleoffset.y = invFloatFactor * (inputcolor.b + inputcolor.a / 255.0 - 0.498); scaleoffset.x *= scale_x; scaleoffset.y *= scale_y; 
#else
 scaleoffset.x = inputcolor.x * scale_x; scaleoffset.y = inputcolor.y * scale_y; 
#endif
 highp vec4 localcolor = vec4(0.0); if (isRemove == 1) { localcolor = texture2D(inputImageTexture, textureCoordinate); } else { localcolor = texture2D(inputImageTexture, textureCoordinate + scaleoffset); } highp vec4 endcolor = vec4(0.0); 
#if defined FLOATTOBYTE
 highp vec2 newoffset = vec2(0.0); newoffset.x = inputcolor.r + inputcolor.g / 255.0 + localcolor.r + localcolor.g / 255.0 - 0.498; newoffset.y = inputcolor.b + inputcolor.a / 255.0 + localcolor.b + localcolor.a / 255.0 - 0.498; highp float x_tmp = floor(newoffset.x * 255.0); highp float y_tmp = floor(newoffset.y * 255.0); endcolor.r = x_tmp / 255.0; endcolor.g = newoffset.x * 255.0 - x_tmp; endcolor.b = y_tmp / 255.0; endcolor.a = newoffset.y * 255.0 - y_tmp; 
#else
 endcolor = inputcolor + localcolor; 
#endif
 gl_FragColor = endcolor; }