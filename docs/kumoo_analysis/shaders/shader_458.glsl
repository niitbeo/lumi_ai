//precision highp float;                                            
varying highp vec2 textureCoordinate;                         		 
uniform sampler2D inputImageTexture;                                
uniform float tableCoef[256];                                       
void main()                                                   		 
{                                                                   
   vec4 c = texture2D(inputImageTexture, textureCoordinate);	     
   vec4 c1 = c * 255.0 + 0.5;                                       
   gl_FragColor = vec4(tableCoef[int(c1.r)], tableCoef[int(c1.g)],  
		tableCoef[int(c1.b)], c.a);                                  
}                                                                   
