

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
uniform int InputH;
uniform int InputW;

const vec2 halfCR = vec2(0.5, 0.5);
const vec2 CR = vec2(1.0, 1.0);

vec4 ReduceOp(vec4 a, vec4 b){
    return a + b;
}
void main()
{
vec4 color = vec4(0);

for(int h = 0; h < InputH ; h++){
    float v     = (float(h) + 0.5) /  float(InputH);
    vec4 tmp = texture2D(texture_input, vec2(texcoordOut.x,v));
    color += tmp;
}
color /= vec4(InputH);

gl_FragColor.r = color.r;
gl_FragColor.g = color.g;
gl_FragColor.b = color.b;
gl_FragColor.w = color.w;

}
    