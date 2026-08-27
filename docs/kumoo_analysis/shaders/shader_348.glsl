
       varying vec2 v_texcoord;
       uniform sampler2D edgeMaskTexture;
       uniform sampler2D mattingMaskTexture;
       uniform sampler2D u_texture;
       uniform vec4 maskEdgeColor;
       void main()
       {
           vec4 orgColor = texture2D(u_texture, v_texcoord);
           vec4 edgeMaskColor = texture2D(edgeMaskTexture, v_texcoord);
           vec4 mattingMaskColor = texture2D(mattingMaskTexture, v_texcoord);
           if (edgeMaskColor.r > mattingMaskColor.r) {
            gl_FragColor = vec4(edgeMaskColor.r);
           }
           else {
            gl_FragColor = vec4(mattingMaskColor.r);
           }
       }
    