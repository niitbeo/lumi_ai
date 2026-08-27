uniform sampler2D inputImageTexture; uniform sampler2D localOffsetTexture; varying vec2 textureCoordinate; varying vec2 textureCoordinate2; 
#if defined FLOATTOBYTE
 uniform float offsetCoef; uniform float offsetBase; 
#endif
 void main() { highp vec4 inputVal = texture2D(localOffsetTexture, textureCoordinate2); highp vec2 globalOffset = vec2(0.0); 
#if defined FLOATTOBYTE
 globalOffset.x = 0.25 * (inputVal.r + inputVal.g / offsetCoef - offsetBase); globalOffset.y = 0.25 * (inputVal.b + inputVal.a / offsetCoef - offsetBase); 
#else
 globalOffset = inputVal.xy; 
#endif
 highp vec4 localVal = texture2D(inputImageTexture, textureCoordinate + globalOffset.xy); highp vec4 mergeOffset = vec4(0.0); 
#if defined FLOATTOBYTE
 highp vec2 newoffset = vec2(0.0); newoffset.x = inputVal.r + inputVal.g / offsetCoef + localVal.r + localVal.g / offsetCoef - offsetBase; newoffset.y = inputVal.b + inputVal.a / offsetCoef + localVal.b + localVal.a / offsetCoef - offsetBase; highp float x_tmp = floor(newoffset.x * offsetCoef); highp float y_tmp = floor(newoffset.y * offsetCoef); mergeOffset.r = x_tmp / offsetCoef; mergeOffset.g = newoffset.x * offsetCoef - x_tmp; mergeOffset.b = y_tmp / offsetCoef; mergeOffset.a = newoffset.y * offsetCoef - y_tmp; 
#else
 mergeOffset.xy = inputVal.xy + localVal.xy; 
#endif
 gl_FragColor = mergeOffset; }