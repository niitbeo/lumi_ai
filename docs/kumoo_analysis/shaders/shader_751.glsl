
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

uniform vec4 u_debugColor;

void main()
{
    gl_FragColor = u_debugColor;
}
