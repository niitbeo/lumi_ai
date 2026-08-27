varying highp vec2 textureCoordinate;                             
uniform sampler2D inputImageTexture;                           
uniform highp vec4 vecParam;                                    
                                                                  
void main()                                                       
{                                                              
   vec2 OF = texture2D(inputImageTexture, textureCoordinate).xy;        
   float w = vecParam.r;        
   float h = vecParam.g;        
   float sx = vecParam.b;        
   float sy = vecParam.a;        
   float x = textureCoordinate.x;        
   float y = textureCoordinate.y;        
   float borderx = 1.0/w;        
   float bordery = 1.0/h;        
   float onex = 1.0/w;        
   float oney = 1.0/h;        
   float alphax = clamp((x-onex)/borderx, 0.0, 1.0) * clamp((1.0-x+onex)/borderx, 0.0, 1.0);        
   float alphay = clamp((y-oney)/bordery, 0.0, 1.0) * clamp((1.0-y+oney)/bordery, 0.0, 1.0);        
   gl_FragColor = vec4(OF.x*alphax*sx, OF.y*alphay*sy, 0, 1.0);        
}                                                              
