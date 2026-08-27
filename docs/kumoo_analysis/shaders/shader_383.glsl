
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
        uniform sampler2D effectTexture;
        uniform float alpha;
        varying vec2 v_texcoord;
        void main() {
            vec4 oriColor = texture2D(u_texture, v_texcoord);
            vec4 effectColor = texture2D(effectTexture, v_texcoord);
            gl_FragColor = mix(oriColor, effectColor, effectColor.a * alpha);
        }
    