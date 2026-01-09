import os
import json
from langchain_upstage import ChatUpstage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from dotenv import load_dotenv

load_dotenv()


class PlotManager:
    def __init__(self):
        self.llm = ChatUpstage(model="solar-pro")
        self.parser = JsonOutputParser()
        self.output_file = "plot.json"

    def process_plot_data(self, input_file="plot_input.json"):
        # 입력 데이터 읽기
        if not os.path.exists(input_file):
            return

        with open(input_file, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
            new_input_text = "\n".join(raw_data.get("sample_plot", []))

        # 기존 분석 결과 읽기
        existing_data = {}
        if os.path.exists(self.output_file):
            with open(self.output_file, 'r', encoding='utf-8') as f:
                try:
                    existing_data = json.load(f)
                except:
                    existing_data = {}

        # AI에게 기존 데이터와 새로운 입력을 주고 업데이트 요청
        prompt = ChatPromptTemplate.from_messages([
            ("system", """당신은 웹소설 편집장입니다. 
            기존 플롯 설정과 작가의 새로운 피드백(입력)을 비교하여 최신화된 플롯을 생성하세요.

            [규칙]
            1. 입력이 전체 시나리오라면 내용을 새로 작성하세요.
            2. 입력이 "누구를 바꿔줘"나 "어디를 수정해" 같은 부분 피드백이라면, 기존 설정을 유지하면서 해당 부분만 지능적으로 수정하세요.
            3. 출력 형식은 반드시 기존 JSON 구조를 유지해야 합니다.

            [기존 설정]
            {existing_data}"""),
            ("human", "작가의 새로운 피드백/시나리오: {new_input}")
        ])

        chain = prompt | self.llm | self.parser
        updated_result = chain.invoke({
            "existing_data": json.dumps(existing_data, ensure_ascii=False),
            "new_input": new_input_text
        })

        # 결과 저장
        with open(self.output_file, 'w', encoding='utf-8') as f:
            json.dump(updated_result, f, ensure_ascii=False, indent=4)

        print(f"작가의 의도를 반영하여 {self.output_file}이 업데이트되었습니다.")
        return updated_result