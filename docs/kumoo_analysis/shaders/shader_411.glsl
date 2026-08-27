
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

    uniform sampler2D inputImageTexture;
    varying vec2 textureCoordinate;

    void main() {
        gl_FragColor = texture2D(inputImageTexture, textureCoordinate);
    }
