
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
varying vec2 v_texCoord;
uniform sampler2D u_texture;

void main()
{
    vec4 color = texture2D(u_texture,v_texCoord);
    gl_FragColor = vec4(vec3(color.r * 0.299 + color.g * 0.587 + color.b * 0.114), 1.0);
}