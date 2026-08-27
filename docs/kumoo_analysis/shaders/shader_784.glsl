
      attribute vec2 a_position;
      varying vec2 v_texcoord;
      varying vec2 v_coord;
      uniform mat4 u_mvpMatrix;
      uniform mat4 u_texMatrix;

      void main()
      {
          vec4 temp = u_texMatrix * vec4(a_position, 0.0, 1.0);
          v_texcoord = temp.xy;
          gl_Position = u_mvpMatrix * vec4(a_position, 0.0, 1.0);
          v_coord = gl_Position.xy;
      }