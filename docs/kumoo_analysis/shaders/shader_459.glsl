varying highp vec2 textureCoordinate;                                            
uniform sampler2D inputImageTexture;                                             
uniform vec3 matWarp[2];                                                         
uniform vec2 sizeImage;                                                          
uniform vec2 texOffset;                                                          
                                                              	                  
void main()                                                   	                  
{                                                                                
   vec3 img_pos = vec3(floor(textureCoordinate * sizeImage), 1.0);               
   vec2 input_coord = vec2(dot(img_pos, matWarp[0]), dot(img_pos, matWarp[1]));  
   input_coord = input_coord * texOffset;			                              
                                                                   			  
   gl_FragColor = texture2D(inputImageTexture, input_coord);                     
}                                                                                
