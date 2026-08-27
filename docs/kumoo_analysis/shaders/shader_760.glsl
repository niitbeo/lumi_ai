p
        #define lowp
        #endif

         uniform sampler2D u_texture;
         varying vec2 v_texcoord;
         uniform float fsize;
         uniform int renderType;

         vec2 textureCoordinate = v_texcoord;

         vec4 gaussH()
         {
             vec4 sum = vec4(0.0);
             sum += texture2D(u_texture, textureCoordinate + vec2(0,-fsize*4.0)) * 0.05;
             sum += texture2D(u_texture, textureCoordinate + vec2(0,-fsize*3.0)) * 0.09;
             sum += texture2D(u_texture, textureCoordinate + vec2(0,-fsize*2.0)) * 0.12;
             sum += texture2D(u_texture, textureCoordinate + vec2(0,-fsize)) * 0.15;
             sum += texture2D(u_texture, textureCoordinate) * 0.18;
             sum += texture2D(u_texture, textureCoordinate + vec2(0,fsize)) * 0.15;
             sum += texture2D(u_texture, textureCoordinate + vec2(0,fsize*2.0)) * 0.12;
             sum += texture2D(u_texture, textureCoordinate + vec2(0,fsize*3.0)) * 0.09;
             sum += texture2D(u_texture, textureCoordinate + vec2(0,fsize*4.0)) * 0.05;
             return sum;
         }

        vec4 gaussV()
        {
            vec4 sum = vec4(0.0);
            sum += texture2D(u_texture, textureCoordinate + vec2(-4.0*fsize, 0.0)) * 0.05;
            sum += texture2D(u_texture, textureCoordinate + vec2(-3.0*fsize, 0.0)) * 0.09;
            sum += texture2D(u_texture, textureCoordinate + vec2(-2.0*fsize, 0.0)) * 0.12;
            sum += texture2D(u_texture, textureCoordinate + vec2(-1.0*fsize, 0.0)) * 0.15;
            sum += texture2D(u_texture, textureCoordinate) * 0.18;
            sum += texture2D(u_texture, textureCoordinate + vec2( 1.0*fsize, 0.0)) * 0.15;
            sum += texture2D(u_texture, textureCoordinate + vec2( 2.0*fsize, 0.0)) * 0.12;
            sum += texture2D(u_texture, textureCoordinate + vec2( 3.0*fsize, 0.0)) * 0.09;
            sum += texture2D(u_texture, textureCoordinate + vec2( 4.0*fsize, 0.0)) * 0.05;
            return sum;
        }
         void main()
         {
            if (renderType == 0) {
                gl_FragColor = gaussH();
            } else {
                gl_FragColor = gaussV();
            }
         }
    