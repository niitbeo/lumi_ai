

    void main() {
        float stepX = texelOffsetStep.x / offsetWH.x;
        float stepY = texelOffsetStep.y / offsetWH.y;

        lowp float definedRad = floor(filterRadius);
        /// GL_FLOAT_TEXTURE GL_NEAREST
        float fX = inputTextureCoordinate.x - (definedRad - 0.5) * stepX;
        float tX = inputTextureCoordinate.x + (definedRad - 0.5) * stepX;
        float fY = inputTextureCoordinate.y - (definedRad + 0.5) * stepY;
        float tY = inputTextureCoordinate.y + (definedRad + 0.5) * stepY;
        float cX = fX;
        float cY = fY;
    #if defined XFILTER
        cY = inputTextureCoordinate.y - 0.5 * stepY;
    #elif defined YFILTER
        cX = inputTextureCoordinate.x - 0.5 * stepX;
    #endif

        vec2 sum = vec2(0.0, 0.0);
        for (int j = 0; j <= 2 * int(definedRad); ++j) {
            sum += texture2D(inputOffsetTexture, vec2(cX, cY)).xy;
            #if defined XFILTER
                cX += stepX;
            #elif defined YFILTER
                cY += stepY;
            #endif
        }

        float weight = filterRadius - definedRad;  // fract(filterRadius);
    #if defined XFILTER
        float stepOffsetx = 0.5 * (1.0 + weight) * stepX;
        sum += weight *
               texture2D(inputOffsetTexture, vec2(fX - stepOffsetx, cY)).xy;
        sum += weight *
               texture2D(inputOffsetTexture, vec2(tX + stepOffsetx, cY)).xy;
    #elif defined YFILTER
        float stepOffsety = 0.5 * (1.0 + weight) * stepY;
        sum += weight *
               texture2D(inputOffsetTexture, vec2(cX, fY - stepOffsety)).xy;
        sum += weight *
               texture2D(inputOffsetTexture, vec2(cX, tY + stepOffsety)).xy;
    #endif

        float div = 2.0 * filterRadius + 1.0;

        offsetCoord = vec4(sum.x / div, sum.y / div, 0.0, 0.0);
    #if defined OFFSETWH
        offsetCoord.xy /= offsetWH;
    #endif
        gl_Position = vec4(inputTextureCoordinate.x * 2.0 - 1.0,
                               inputTextureCoordinate.y * 2.0 - 1.0, 0.0, 1.0);
    }
