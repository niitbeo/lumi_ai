
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
        uniform int type;
        void main()
        {
            vec4 oriColor = texture2D(u_texture, textureCoordinate);
            float dstColor = 0.0;
            if (type == 0) {
                dstColor = oriColor.r;
            }else if(type == 1) {
                dstColor = oriColor.g;
            }else if(type == 2) {
                dstColor = oriColor.b;
            }else if(type == 3) {
                dstColor = oriColor.a;
            }
            gl_FragColor = vec4(vec3(oriColor.r), 1.0);
        }
    