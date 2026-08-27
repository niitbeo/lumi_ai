
                attribute vec2 position;
                attribute vec2 inputTextureCoordinate;

#ifdef MEITU_SHARPEN_VERSION_0
                uniform float imageWidthFactor;
                uniform float imageHeightFactor;
                uniform float sharpness;
                
                varying vec2 textureCoordinate;
                varying vec2 leftTextureCoordinate;
                varying vec2 rightTextureCoordinate;
                varying vec2 topTextureCoordinate;
                varying vec2 bottomTextureCoordinate;
                
                varying float centerMultiplier;
                varying float edgeMultiplier;
                
                void main()
                {
                    gl_Position = vec4(position, 0.0, 1.0);
                    
                    vec2 widthStep = vec2(imageWidthFactor, 0.0);
                    vec2 heightStep = vec2(0.0, imageHeightFactor);
                    
                    textureCoordinate = inputTextureCoordinate;
                    leftTextureCoordinate = inputTextureCoordinate - widthStep;
                    rightTextureCoordinate = inputTextureCoordinate + widthStep;
                    topTextureCoordinate = inputTextureCoordinate + heightStep;
                    bottomTextureCoordinate = inputTextureCoordinate - heightStep;
                    
                    centerMultiplier = 1.0 + 4.0 * sharpness;
                    edgeMultiplier = sharpness;
                }
#endif

#ifdef MEITU_SHARPEN_VERSION_1
        varying vec2 v_texCoord;

        void main()
        {
          gl_Position = vec4(position, 0.0, 1.0);
          v_texCoord = inputTextureCoordinate;
        }
#endif
                