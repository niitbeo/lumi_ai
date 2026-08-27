
    #endif

    void main() {
        gl_Position = vec4(userTextureCoordinate.x * 2.0 - 1.0,
                       userTextureCoordinate.y * 2.0 - 1.0, 0.0, 1.0);

        userCoord = userTextureCoordinate.xy;
        maskCoord = maskTextureCoordinate.xy;

        #if defined FACESCALEPOINT
            FaceScaleRadiusOut = userFaceScaleRadius;
        #endif

        #if defined OFFSETRESAMPLE
            vec4 maskResample = mask_projection * mask_modelview *
                        vec4(offsetTextureCoordinate, 0.0, 1.0);
            offsetCoord = maskResample.xy;
        #else
            offsetCoord = offsetTextureCoordinate.xy;
        #endif
    }
