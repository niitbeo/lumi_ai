
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
uniform sampler2D u_downTexture;
uniform sampler2D u_downResTexture;
uniform float f_alpha;
uniform float f_type;
void main(){
    vec4 sorce = texture2D(u_texture, v_texcoord);
    vec4 down = vec4(0.0);
    vec4 downRes = texture2D(u_downResTexture, v_texcoord);
    if (f_type > 0.5) {
        down = texture2D(u_downTexture, v_texcoord);
    } else {
        down = sorce;
    }
    vec4 resColor = sorce - down + downRes;
    vec3 retColor = mix(sorce.rgb, resColor.rgb, f_alpha);
    gl_FragColor = vec4(retColor.rgb, sorce.a);
}