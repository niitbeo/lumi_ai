attribute vec3 a_position;
attribute vec2 a_texcoord;
uniform mat4 u_mvpMatrix;
varying vec2 texcoordOut;

void main() {
	texcoordOut = a_texcoord;
	gl_Position = u_mvpMatrix * vec4(a_position, 1.0);
}