 1.0

    #ifdef BOUNDLIMIT
    uniform float u_limitBound1;
    uniform float u_limitBound2;
    float smoothCoord(vec2 coord, float r1, float r2) {
        vec2 center = vec2(0.5, 0.5);
        vec2 dist = abs(coord - center);

        float maxDist1 = 0.5;
        float maxDist2 = maxDist1 - r1 / 2.0;
        float maxDist3 = maxDist1 - r2 / 2.0;

        float distToCenter = max(dist.x, dist.y);

        if (distToCenter <= maxDist3) {
            return 1.0;
        } else if (distToCenter <= maxDist2) {
            return (maxDist2 - distToCenter) / (maxDist2 - maxDist3);
        } else if (distToCenter <= maxDist1) {
            return 0.0;
        } else {
            return 0.0;
        }
    }
    #endif

    void main() {
        vec4 offsetValue = texture2D(inputImageTexture2, offsetCoord.xy);
        vec2 offsetVec = offsetValue.xy;
        #if defined FLOATTOBYTE
            float x = offsetValue.r * 255.0 + offsetValue.g;
            float y = offsetValue.b * 255.0 + offsetValue.a;
            offsetVec.x = 0.25 * x / 255.0 - 0.1245;
            offsetVec.y = 0.25 * y / 255.0 - 0.1245;
        #endif

        #if defined FACESCALEPOINT
            offsetVec.x *= FaceScaleRadiusOut.x;
            offsetVec.y *= FaceScaleRadiusOut.y;
        #elif defined FACESCALEPIC
            offsetVec.x *= min(1.0, faceSizeScale.x);
            offsetVec.y *= min(1.0, faceSizeScale.y);
        #endif
        offsetVec *= transformMatrix;

        float degree = texture2D(degreeMaskTexture, maskCoord).r;
        degree = degree * degree * offsetAlpha;
        // vec2 radius = (offsetCoord - vec2(0.5, 0.5)) * 2.0;
        // float boundAlpha = clamp((1.0 - dot(radius, radius)), 0.0, 1.0);

        vec2 res_uv = userCoord;
        #ifdef BOUNDLIMIT
            res_uv += offsetVec * degree * smoothCoord(userCoord, u_limitBound1, u_limitBound2);
        #else
            res_uv += offsetVec * degree;
        #endif
        gl_FragColor = texture2D(inputImageTexture, res_uv);
    }
