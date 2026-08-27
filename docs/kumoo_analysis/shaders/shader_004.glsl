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

uniform sampler2D u_texture;
varying vec2 texcoordOut;

void main() {
	gl_FragColor = texture2D(u_texture, texcoordOut);
}