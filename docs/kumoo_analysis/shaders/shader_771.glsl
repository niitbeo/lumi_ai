
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
         uniform sampler2D tempTexture;
         uniform sampler2D maskTexture;
         varying vec2 v_texcoord;
         uniform int maskChannel;
         uniform int maskReverse;
         void main()
         {
              vec4 srcColor = texture2D(u_texture,v_texcoord);
              vec4 tempColor = texture2D(tempTexture,v_texcoord);
              vec4 maskColor = texture2D(maskTexture,v_texcoord);
              vec4 destColor = vec4(0.0);

              float maskAlpha = maskColor.r;
              if (maskChannel == 1) { // CMTIKMaskChannelType::Alpha
                maskAlpha = maskColor.a;
              }

              if (maskReverse == 1) {
                maskAlpha = 1.0 - maskAlpha;
              }

              destColor.rgb = mix(tempColor.rgb,srcColor.rgb,maskAlpha);
              destColor.a = srcColor.a;
              gl_FragColor = destColor;
         }
    