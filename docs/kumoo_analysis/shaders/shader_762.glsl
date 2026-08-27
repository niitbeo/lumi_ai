
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
        varying vec2 v_texcoord;
        void main() {
            vec4 oriColor = texture2D(u_texture, v_texcoord);
            vec4 destColor = vec4(1.0);
            destColor.r = 0.299 * oriColor.r + 0.587 * oriColor.g + 0.114 * oriColor.b;
            destColor.g = 0.299 * oriColor.r + 0.587 * oriColor.g + 0.114 * oriColor.b;
            destColor.b = 0.299 * oriColor.r + 0.587 * oriColor.g + 0.114 * oriColor.b;
            destColor.a = 1.0;
            gl_FragColor = destColor;
        }
    