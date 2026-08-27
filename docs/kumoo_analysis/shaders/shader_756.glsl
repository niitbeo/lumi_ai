
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
        void main()
        {
            if (v_texcoord.x > 1.0 || v_texcoord.x < 0.0 || v_texcoord.y > 1.0 || v_texcoord.y < 0.0 ) {
                gl_FragColor = vec4(0.0, 0.0, 0.0, 0.0);
            } else {
                gl_FragColor = texture2D(u_texture,v_texcoord);
            }
        }
    