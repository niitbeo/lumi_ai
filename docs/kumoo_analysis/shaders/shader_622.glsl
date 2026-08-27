uniform sampler2D inputOffsetTexture; uniform mediump float alpha; varying vec2 textureCoordStart; varying vec2 textureCoordEnd; 
#if defined FLOATTOBYTE
 uniform highp float floatFactor; 
#endif
 void main() { highp vec2 faceOffset = textureCoordStart - textureCoordEnd; faceOffset *= alpha; highp vec4 inputcolor = texture2D(inputOffsetTexture, textureCoordEnd); highp vec4 endcolor = vec4(0.0); 
#if defined FLOATTOBYTE
 highp vec2 newoffset = vec2(0.0); newoffset.x = inputcolor.r + inputcolor.g / 255.0 + faceOffset.x * floatFactor; newoffset.y = inputcolor.b + inputcolor.a / 255.0 + faceOffset.y * floatFactor; float x_tmp = floor(newoffset.x * 255.0); float y_tmp = floor(newoffset.y * 255.0); endcolor.r = x_tmp / 255.0; endcolor.g = newoffset.x * 255.0 - x_tmp; endcolor.b = y_tmp / 255.0; endcolor.a = newoffset.y * 255.0 - y_tmp; 
#else
 endcolor.xy = inputcolor.xy + faceOffset; 
#endif
 gl_FragColor = endcolor; }