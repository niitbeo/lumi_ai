g out which grid cell the incoming pixel located
    float xsb = floor(xs);
    float ysb = floor(ys);
    float zsb = floor(zs);
    
    // Un-stretch the coord and xb,yb,zb is the cell origin in normal coord system
    float squishOffset = (xsb + ysb + zsb) * SQUISH_CONSTANT_3D;
    float xb = xsb + squishOffset;
    float yb = ysb + squishOffset;
    float zb = zsb + squishOffset;
    
    // xins, yins, zins is the distance from cell origin in stretched coord system
    float xins = fract(xs);
    float yins = fract(ys);
    float zins = fract(zs);
    
    float inSum = xins + yins + zins;
    
    // Distance from cell origin in normal coord system.
    float dx = x - xb;
    float dy = y - yb;
    float dz = z - zb;
    // Switching between 3 regions

    vec3 value =  compare(inSum - 2.0, compare(inSum - 1.0, firstRegion(xsb, ysb, zsb, dx, dy, dz, chroma), 
        secondRegion(xsb, ysb, zsb, dx, dy, dz, chroma)), thirdRegion( xsb, ysb, zsb, dx, dy, dz, chroma));
    return value * NORM_CONSTANT_3D;
}



vec4 simplifiedOpenSimplex(float seed, float grainSize, float layer2SizeFactor, float layer3SizeFactor,
 float layer1Weight, float layer2Weight, float layer3Weight, float chroma){
     
     vec2 dc = v_texCoord ;//* vec2(Width,Height);
     dc.x *= Width;
     dc.y = (1.0-dc.y)*Height;

     //return texture2D(lookupTable, vec2(mod(dc.x, 256.0)/256.0,mod(dc.y, 256.0)/257.0));

     float layer2SeedOffset = 5.0;
     float layer3SeedOffset = 10.0;
     
     vec3 result = simplifiedOpenSimplexOnePass( dc, grainSize, seed, chroma) * layer1Weight;
     
     result += simplifiedOpenSimplexOnePass(dc, grainSize * layer2SizeFactor, seed + layer2SeedOffset, chroma) * layer2Weight;
     result += simplifiedOpenSimplexOnePass(dc, grainSize * layer3SizeFactor, seed + layer3SeedOffset, chroma) * layer3Weight;
     result *= 1.0 / (layer1Weight + layer2Weight + layer3Weight);
     // re-normalized to [0,1] from [-1,1]
     return vec4((result + 1.0) * 0.5, 1.0);
 }

void main()
{
    vec4 detail = simplifiedOpenSimplex(141.75,GrainSize,1.5,2.0,3.0,2.0,1.0,0.0);
   // vec4 detail = texture2D(lookupTable,vec2(1.0,v_texCoord.y));
   gl_FragColor = vec4(detail.rgb,1.0);
  // gl_FragColor = vec4(detail.rgb,1.0);
//gl_FragColor = vec4(texture2D(lookupTable,v_texCoord).rgb, 1.0);
}
                