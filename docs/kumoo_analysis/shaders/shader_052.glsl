
#ifdef GL_ES//for discriminate GLES & GL
    #ifdef GL_FRAGMENT_PRECISION_HIGH
        precision highp float;
    #else
        precision mediump float;
    #endif
#else
    #define highp
    #define mediump
    #define lowp
#endif
varying vec2 texcoordOut;
uniform sampler2D texture_input;
uniform sampler2D texture_lut;
void main()
{
// gl_FragColor = texture2D(texture_input, texcoordOut);
// texturelut