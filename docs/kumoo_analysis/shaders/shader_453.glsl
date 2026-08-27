

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
uniform sampler2D texture_sum;
uniform float mask_mean;

const vec2 halfCR = vec2(0.5, 0.5);
const vec2 CR = vec2(1.0, 1.0);


void main()
{
vec4 color_mean = texture2D(texture_sum,vec2(0,0));

if (color_mean.x < mask_mean) {
  gl_FragColor = vec4(0.0);
} else {
  gl_FragColor = texture2D(texture_input, texcoordOut);
}

}
    