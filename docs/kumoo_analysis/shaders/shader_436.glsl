
    attribute vec3 a_position;
    attribute vec2 a_texcoord;
    varying vec2 v_texcoord;
    uniform mat4 u_mvpMatrix;
    varying highp vec2 vGlitterPatternTexcoord1;
    varying highp vec2 vGlitterPatternTexcoord2;
    varying highp vec2 vGlitterPatternTexcoord3;
    void main()
    {
        v_texcoord = a_texcoord;
        gl_Position = u_mvpMatrix * vec4(a_position,1.0);
        vec2 glitterPatternScale = vec2(10.5,10.9);
        vGlitterPatternTexcoord1 = v_texcoord * glitterPatternScale;
        const mediump mat3 kRotateAndShift1 = mat3(0.70711, 0.70711, 0.00000,
        -0.70711, 0.70711, 0.00000,
        0.50000, -0.20711, 1.00000);
        vGlitterPatternTexcoord2 = (kRotateAndShift1 * vec3(v_texcoord * glitterPatternScale, 1.0)).xy;
        const mediump mat3 kRotateAndShift2 = mat3(0.96593, 0.25882, 0.00000,
        -0.25882, 0.96593, 0.00000,
        0.14645, -0.11237, 1.00000);
        vGlitterPatternTexcoord3 = (kRotateAndShift2 * vec3(v_texcoord * glitterPatternScale, 1.0)).xy;
    }
