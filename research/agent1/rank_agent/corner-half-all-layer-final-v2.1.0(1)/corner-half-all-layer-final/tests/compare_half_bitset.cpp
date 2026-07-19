#include <array>
#include <bit>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <queue>
#include <stdexcept>
#include <string>
#include <vector>

static bool occupied(char c){return c!='-';}
static bool nonpin(char c){return c=='S'||c=='c';}
static uint32_t cell_bits(char c){
  switch(c){case '-':return 0;case 'S':return 1;case 'P':return 2;case 'c':return 3;}
  throw std::runtime_error("bad cell");
}
static bool stable_pair(const std::string& a,const std::string& b,int cap){
    std::vector<std::array<char,2>> x(cap, {'-','-'});
    for(int l=0;l<cap;l++){
        if(l<(int)a.size())x[l][0]=a[l];
        if(l<(int)b.size())x[l][1]=b[l];
    }
    std::vector<std::array<uint8_t,2>> sup(cap, {0,0});
    std::queue<std::pair<int,int>> q;
    for(int c=0;c<2;c++) if(occupied(x[0][c])){sup[0][c]=1;q.push({0,c});}
    while(!q.empty()){
        auto [l,c]=q.front();q.pop();
        if(l+1<cap && occupied(x[l+1][c]) && !sup[l+1][c]){
            sup[l+1][c]=1;q.push({l+1,c});
        }
        int d=1-c;
        if(nonpin(x[l][c]) && nonpin(x[l][d]) && !sup[l][d]){
            sup[l][d]=1;q.push({l,d});
        }
        if(l>0 && x[l][c]=='c' && x[l-1][c]=='c' && !sup[l-1][c]){
            sup[l-1][c]=1;q.push({l-1,c});
        }
    }
    for(int l=0;l<cap;l++)for(int c=0;c<2;c++)
        if(occupied(x[l][c])&&!sup[l][c])return false;
    return true;
}
static uint32_t key_of(const std::string&a,const std::string&b,int cap){
  uint32_t key=0;
  for(int l=0;l<cap;l++){
    const char ca=l<(int)a.size()?a[l]:'-';
    const char cb=l<(int)b.size()?b[l]:'-';
    key |= cell_bits(ca) << (4*l);
    key |= cell_bits(cb) << (4*l+2);
  }
  return key;
}
int main(int argc,char**argv){
  if(argc!=4){std::cerr<<"usage: compare CAP COLUMNS HALFBIT\n";return 2;}
  const int cap=std::stoi(argv[1]);
  std::ifstream cf(argv[2]);std::vector<std::string> cols;std::string s;
  while(std::getline(cf,s)){if(s=="<EMPTY>")s.clear();cols.push_back(s);}
  std::ifstream in(argv[3],std::ios::binary);
  uint32_t magic=0,layers=0;uint64_t oracle_count=0;
  in.read(reinterpret_cast<char*>(&magic),4);in.read(reinterpret_cast<char*>(&layers),4);
  in.read(reinterpret_cast<char*>(&oracle_count),8);
  if(magic!=0x48414c46u||layers!=(uint32_t)cap)throw std::runtime_error("bad halfbit");
  const uint64_t nbits=uint64_t(1)<<(4*cap);
  std::vector<uint64_t> oracle((nbits+63)/64),pred((nbits+63)/64);
  in.read(reinterpret_cast<char*>(oracle.data()),oracle.size()*8);
  uint64_t predicted_count=0;
  for(const auto&a:cols)for(const auto&b:cols)if(stable_pair(a,b,cap)){
    uint32_t k=key_of(a,b,cap);uint64_t bit=uint64_t(1)<<(k&63);
    if(!(pred[k>>6]&bit)){pred[k>>6]|=bit;predicted_count++;}
  }
  uint64_t fp=0,fn=0;uint32_t first_fp=UINT32_MAX,first_fn=UINT32_MAX;
  for(uint64_t i=0;i<oracle.size();i++){
    uint64_t p=pred[i],o=oracle[i];
    uint64_t fpm=p&~o,fnm=o&~p;
    fp+=std::popcount(fpm);fn+=std::popcount(fnm);
    if(first_fp==UINT32_MAX&&fpm)first_fp=uint32_t(64*i+std::countr_zero(fpm));
    if(first_fn==UINT32_MAX&&fnm)first_fn=uint32_t(64*i+std::countr_zero(fnm));
  }
  std::cout<<"{\"cap\":"<<cap<<",\"columns\":"<<cols.size()
           <<",\"oracle\":"<<oracle_count<<",\"predicted\":"<<predicted_count
           <<",\"false_positive\":"<<fp<<",\"false_negative\":"<<fn;
  if(first_fp!=UINT32_MAX)std::cout<<",\"first_fp_key\":"<<first_fp;
  if(first_fn!=UINT32_MAX)std::cout<<",\"first_fn_key\":"<<first_fn;
  std::cout<<"}\n";
  return (fp||fn)?1:0;
}
