
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
    if (color.a > 0.0) {
        color = vec4(clamp(color.rgb / color.a, 0.0, 1.0), color.a);
    }
    gl_FragColor = color;
}