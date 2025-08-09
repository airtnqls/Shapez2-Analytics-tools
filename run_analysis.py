#!/usr/bin/env python3
"""
Claw 분석을 실행하는 스크립트
입력 파일을 분석하여 claw 처리에 실패한 도형들을 출력 파일에 저장합니다.
"""

from claw_tracer import _log
from shape_analyzer import analyze_shape
from shape import Shape
from i18n import _
import sys
import os

def analyze_claws_from_file(input_filepath: str, output_filepath: str):
    """
    주어진 입력 파일에서 도형 코드를 읽어 클로 가능/불가능을 판별하고,
    클로 불가능한 도형 코드만 새 파일에 저장합니다.
    """
    _log(f"DEBUG: {_('run_analysis.start', input_filepath=input_filepath)}")
    
    impossible_shapes = []
    total_shapes = 0
    
    try:
        with open(input_filepath, 'r', encoding='utf-8') as infile:
            for line_num, line in enumerate(infile, 1):
                shape_code = line.strip()
                if not shape_code:
                    continue
                
                total_shapes += 1
                
                try:
                    shape_obj = Shape.from_string(shape_code)
                    result, reason = analyze_shape(shape_code, shape_obj)
                    
                    # "클로불가능" 또는 "클로 룰1" 또는 "클로 룰2"가 사유에 포함된 경우 불가능으로 간주
                    if "불가능" in reason or "클로 룰" in reason or "불가능" in result:
                        impossible_shapes.append(shape_code)
                        _log(f"DEBUG: {_('run_analysis.claw_impossible', shape_code=shape_code, reason=reason)}")
                    else:
                        _log(f"DEBUG: {_('run_analysis.claw_possible', shape_code=shape_code, reason=reason)}")
                        
                except Exception as e:
                    _log(f"ERROR: {_('run_analysis.error.processing', shape_code=shape_code, line_num=line_num, error=str(e))}")
                    impossible_shapes.append(f"{shape_code} # 오류 발생: {e}")
                    
    except FileNotFoundError:
        _log(f"ERROR: {_('run_analysis.error.file_not_found', input_filepath=input_filepath)}")
        return
    except Exception as e:
        _log(f"ERROR: {_('run_analysis.error.file_read', error=str(e))}")
        return
        
    _log(f"DEBUG: {_('run_analysis.summary', total_shapes=total_shapes, impossible_count=len(impossible_shapes))}")
    
    try:
        with open(output_filepath, 'a', encoding='utf-8') as outfile:
            for shape_code in impossible_shapes:
                outfile.write(shape_code + '\n')
        _log(f"DEBUG: {_('run_analysis.success.write', output_filepath=output_filepath)}")
    except Exception as e:
        _log(f"ERROR: {_('run_analysis.error.write', output_filepath=output_filepath, error=str(e))}")

def main():
    # 기본 파일 경로 설정
    input_file = 'data/all40171clawsnohybrid.txt'
    output_file = 'data/claw_impossible_shapes.txt'
    
    # 명령행 인수가 제공된 경우 사용
    if len(sys.argv) >= 2:
        input_file = sys.argv[1]
    if len(sys.argv) >= 3:
        output_file = sys.argv[2]
    
    # 입력 파일 존재 확인
    if not os.path.exists(input_file):
        print(f"오류: 입력 파일 '{input_file}'을 찾을 수 없습니다.")
        sys.exit(1)
    
    # 출력 디렉토리 생성
    output_dir = os.path.dirname(output_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 기존 출력 파일이 있다면 삭제하여 덮어쓰기 준비
    if os.path.exists(output_file):
        os.remove(output_file)
    
    print(f"분석을 시작합니다...")
    print(f"입력 파일: {input_file}")
    print(f"출력 파일: {output_file}")
    
    try:
        analyze_claws_from_file(input_file, output_file)
        print("분석이 완료되었습니다.")
        
        # 결과 파일 크기 확인
        if os.path.exists(output_file):
            with open(output_file, 'r') as f:
                lines = f.readlines()
            print(f"발견된 claw 처리 불가능한 도형 수: {len(lines)}")
        
    except Exception as e:
        print(f"분석 중 오류가 발생했습니다: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 