
#ifdef GL_ES
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
varying vec2 v_texcoord;
uniform sampler2D u_texture;

void main(){
    vec4 color = texture2D(u_texture, v_texcoord);
    color.r = color.r * color.a;
    color.g = color.g * color.a;
    color.b = color.b * color.a;
    gl_FragColor = color;
}