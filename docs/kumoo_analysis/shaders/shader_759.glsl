
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

varying vec3 v_normal;

void main() {
    gl_FragColor = vec4(v_normal * vec3(0.5) + vec3(0.5), 1.0);
}
