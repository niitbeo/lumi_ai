
                attribute vec4  position;
                attribute vec2  inputTextureCoordinate;
                attribute vec2  inputTextureCoordinate2;
                varying   vec2  glv_TextureCoords;
                varying   vec2  glv_TextureCoords1;
                void main()
               {
                   gl_Position = position;
                   glv_TextureCoords = inputTextureCoordinate;
                   glv_TextureCoords1 = inputTextureCoordinate2;
               }
                