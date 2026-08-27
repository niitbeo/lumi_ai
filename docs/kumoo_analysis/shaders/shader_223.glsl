uniform sampler2D inputImageTexture; varying vec2 textureCoordinate; void main() { highp vec4 inputcolor = texture2D(inputImageTexture, textureCoordinate); highp vec4 endcolor = vec4(0.0); 
#if defined FLOATTOBYTE
 highp vec2 newoffset = vec2(0.0); newoffset.x = 0.996 - inputcolor.r - inputcolor.g / 255.0; newoffset.y = 0.996 - inputcolor.b - inputcolor.a / 255.0; highp float x_tmp = floor(newoffset.x * 255.0); highp float y_tmp = floor(newoffset.y * 255.0); endcolor.r = x_tmp / 255.0; endcolor.g = newoffset.x * 255.0 - x_tmp; endcolor.b = y_tmp / 255.0; endcolor.a = newoffset.y * 255.0 - y_tmp; 
#else
 endcolor = -1.0 * inputcolor; 
#endif
 gl_FragColor = endcolor; }