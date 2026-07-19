#include <algorithm>
#include <array>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <queue>
#include <string>
#include <vector>

static bool occupied(char c){return c!='-';}
static bool nonpin(char c){return c=='S'||c=='c';}

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
        // vertical upward support, any occupied cell
        if(l+1<cap && occupied(x[l+1][c]) && !sup[l+1][c]){
            sup[l+1][c]=1;q.push({l+1,c});
        }
        // horizontal support between non-pins
        int d=1-c;
        if(nonpin(x[l][c]) && nonpin(x[l][d]) && !sup[l][d]){
            sup[l][d]=1;q.push({l,d});
        }
        // a supported crystal can support the crystal directly below (hang)
        if(l>0 && x[l][c]=='c' && x[l-1][c]=='c' && !sup[l-1][c]){
            sup[l-1][c]=1;q.push({l-1,c});
        }
    }
    for(int l=0;l<cap;l++)for(int c=0;c<2;c++)
        if(occupied(x[l][c])&&!sup[l][c])return false;
    return true;
}

int main(int argc,char**argv){
    if(argc!=3){std::cerr<<"usage: count_half_pairs CAP COLUMNS.txt\n";return 2;}
    int cap=std::stoi(argv[1]);
    std::ifstream f(argv[2]);std::string s;std::vector<std::string> cols;
    while(std::getline(f,s)){
        if(s=="<EMPTY>")s.clear();
        cols.push_back(s);
    }
    uint64_t count=0;
    for(const auto&a:cols)for(const auto&b:cols)count+=stable_pair(a,b,cap);
    std::cout<<"cap="<<cap<<" columns="<<cols.size()<<" halves="<<count<<"\n";
}
