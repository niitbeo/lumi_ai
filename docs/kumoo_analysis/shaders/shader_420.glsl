
#ifdef GL_ES//for discriminate GLES & GL
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

///////////////////////////////////////////////////////////
// Uniforms
uniform sampler2D u_texture;
uniform vec2 u_step;


///////////////////////////////////////////////////////////
// Varyings
varying vec2 v_texCoord;
varying vec4 v_color;

void main()
{
    vec4 sum = vec4(0.0);
    float sumWeight = 0.0;

    // float kernel[9];
    // vec2 offset[9];

    // offset[0] = vec2(-u_step.s, -u_step.t);
    // offset[1] = vec2(0.0, -u_step.t);
    // offset[2] = vec2(u_step.s, -u_step.t);

    // offset[3] = vec2(-u_step.s, 0.0);
    // offset[4] = vec2(0.0, 0.0);
    // offset[5] = vec2(u_step.s, 0.0);

    // offset[6] = vec2(-u_step.s, u_step.t);
    // offset[7] = vec2(0.0, u_step.t);
    // offset[8] = vec2(u_step.s, u_step.t);

    // kernel[0] = -1.0;   kernel[1] = -1.0;   kernel[2] = -1.0;
    // kernel[3] = -1.0;   kernel[4] = +9.0;   kernel[5] = -1.0;
    // kernel[6] = -1.0;   kernel[7] = -1.0;   kernel[8] = -1.0;

    // for(int i = 0; i < 9; i++)
    // {
    //     vec4 tmp = texture2D(u_texture, v_texCoord.st + offset[i]);
    //     sum += tmp * kernel[i];
    // }
    float kernel[5];
    vec2 offset[5];

    offset[0] = vec2(0.0, -u_step.t);
    offset[1] = vec2(-u_step.s, 0.0);
    offset[2] = vec2(0.0, 0.0);
    offset[3] = vec2(u_step.s, 0.0);
    offset[4] = vec2(0.0, u_step.t);
    kernel[0] = -1.0;   kernel[1] = -1.0;  
    kernel[2] = 7.0;   kernel[3] = -1.0;
    kernel[4] = -1.0; 


    for(int i = 0; i < 5; i++)
    {
        vec4 tmp = texture2D(u_texture, v_texCoord.st + offset[i]);
        sum += tmp * kernel[i];
        sumWeight += kernel[i];
    }
    gl_FragColor = vec4(sum.rgb/sumWeight, 1.0);

  //  gl_FragColor = texture2D(u_texture, v_texCoord);
}

                