
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
uniform float f_alpha;

void main()
{
    gl_FragColor = texture2D(u_texture, vec2(v_texcoord.x, v_texcoord.y)) * f_alpha;
}
