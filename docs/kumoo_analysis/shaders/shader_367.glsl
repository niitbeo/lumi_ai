
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

         vec2 textureCoordinate = v_texcoord;
         void main()
         {
              vec4 srcColor = texture2D(u_texture, v_texcoord);
              vec4 destColor = vec4(0.0);
              destColor.r = 1.0 - srcColor.r;
              destColor.g = 1.0 - srcColor.g;
              destColor.b = 1.0 - srcColor.b;
              destColor.a = srcColor.a;
              gl_FragColor = destColor;
         }
    