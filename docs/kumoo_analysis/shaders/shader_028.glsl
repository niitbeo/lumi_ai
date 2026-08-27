
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

  varying vec2 v_texCoord;

  uniform sampler2D u_texture;
  uniform sampler2D u_grain;

  uniform float u_max;
  uniform float v_max;

  uniform float ratio;

  uniform float random_x1; // 0 ~ 1
  uniform float random_y1; // 0 ~ 1

  vec3 rgb2gray = vec3(0.299, 0.587, 0.114);

  float check_value(float value)
  {
      float int_part = floor(value);
      value = value - int_part;
      return value;
  }

  float get_grain_texture(vec2 uv, float random_x, float random_y, float u_max, float v_max)
  {
      vec2 res;
      float random_u = check_value(uv.x + random_x);
      float random_v = check_value(uv.y + random_y);

      res.x = check_value(random_u * u_max);
      res.y = check_value(random_v * v_max);
      return texture2D(u_grain, res).r;
  }


  void main()
  {
      vec4 ori_color = texture2D(u_texture, v_texCoord);
      vec3 grain_color;
      float ori_gray = dot(rgb2gray, ori_color.rgb);
      ori_gray = ori_gray * 2.0 - 1.0;
      float abs_ori_gray = abs(ori_gray);
      float abs_ori_gray2 = abs_ori_gray * abs_ori_gray;
      float abs_ori_gray3 = abs_ori_gray2 * abs_ori_gray;

      float grain_gray = get_grain_texture(v_texCoord, random_x1, random_y1, u_max, v_max);

      grain_gray = grain_gray * 2.0 - 1.0;
      float mask;
      float strength = 0.49019608;
      if(ori_gray >= 0.)
      {
          mask = (abs_ori_gray3 * 0.5 + abs_ori_gray2 * 0.5) * (strength - 0.03921569);
      }
      else
      {
          mask = (abs_ori_gray2 * 0.4 + abs_ori_gray * 0.6) * strength;
      }

      vec3 new_color = clamp(ori_color.rgb + grain_gray * (strength - mask), 0., 1.);
      new_color = mix(ori_color.rgb, new_color, ratio);

      gl_FragColor.rgb = new_color;
      gl_FragColor.a = ori_color.a;
  }
