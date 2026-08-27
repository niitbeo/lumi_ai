
attribute vec3 a_position;
attribute vec3 a_normal;

varying vec3 v_normal;

uniform mat4 u_mvpMatrix;

void main() {
    v_normal = a_normal;
    gl_Position = u_mvpMatrix * vec4(a_position, 1.0);
}
