varying vec2 textureCoordinate; uniform sampler2D offsetTexture; uniform sampler2D offsetTexture2; 
#if defined FLOATTOBYTE
 uniform highp float floatFactor; 
#endif
 uniform float isExport; void main() { highp vec4 offsetValue = texture2D(offsetTexture, textureCoordinate); float offsetLen = float(offsetValue.x * offsetValue.x + offsetValue.x * offsetValue.y); vec4 endColor = offsetValue; endColor = offsetValue + texture2D(offsetTexture2, textureCoordinate + offsetValue.xy); endColor = mix(endColor, endColor - offsetValue, isExport); gl_FragColor = endColor; }