import os
import csv
import time
from datetime import datetime
from threading import Lock
import pandas as pd
from typing import Dict, Any, Optional


class PerformanceLogger:
    def __init__(self, log_file="performance_log.csv"):
        self.log_file = log_file
        self.lock = Lock()
        self.fieldnames = [
            'timestamp', 
            'session_id', 
            'asr_time', 
            'llm_time', 
            'tts_time',
            'total_time'
        ]
        self.detailed_fieldnames = [
            'timestamp',
            'session_id',
            'asr_start_time',
            'asr_end_time',
            'asr_duration',
            'llm_start_time',
            'llm_first_token_time',
            'llm_first_duration',
            'llm_end_time',
            'llm_duration',
            'tts_start_time',
            'tts_first_token_time',
            'tts_first_duration',
            'tts_end_time',
            'tts_duration',
            'total_duration'
        ]
        self._initialize_log_file()

    def _initialize_log_file(self):
        """初始化日志文件，如果不存在则创建并写入表头"""
        if not os.path.exists(self.log_file):
            with open(self.log_file, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=self.fieldnames)
                writer.writeheader()

    def log_performance(self, session_id, asr_time=None, llm_time=None, tts_time=None, total_time=None):
        """记录性能数据"""
        with self.lock:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = {
                'timestamp': timestamp,
                'session_id': session_id,
                'asr_time': asr_time,
                'llm_time': llm_time,
                'tts_time': tts_time,
                'total_time': total_time
            }
            
            with open(self.log_file, 'a', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=self.fieldnames)
                writer.writerow(log_entry)

    def log_detailed_performance(self, session_id: str, data: Dict[str, Any]):
        """记录详细的性能数据，包含各个阶段的时间节点"""
        detailed_log_file = self.log_file.replace('.csv', '_detailed.csv')
        
        with self.lock:
            # 如果文件不存在，创建并写入表头
            if not os.path.exists(detailed_log_file):
                with open(detailed_log_file, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=self.detailed_fieldnames)
                    writer.writeheader()
            
            # 准备日志条目
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = {
                'timestamp': timestamp,
                'session_id': session_id,
                **data
            }
            
            # 写入详细性能日志
            with open(detailed_log_file, 'a', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=self.detailed_fieldnames)
                writer.writerow(log_entry)

    def export_to_excel(self, excel_file: Optional[str] = None) -> bool:
        """将性能日志导出为Excel文件"""
        try:
            # 默认Excel文件名
            if excel_file is None:
                excel_file = self.log_file.replace('.csv', '.xlsx')
            
            # 读取详细性能日志
            detailed_log_file = self.log_file.replace('.csv', '_detailed.csv')
            if not os.path.exists(detailed_log_file):
                print(f"详细性能日志文件 {detailed_log_file} 不存在")
                return False
            
            # 读取CSV数据
            df = pd.read_csv(detailed_log_file)
            
            # 导出为Excel
            df.to_excel(excel_file, index=False, sheet_name='Performance Data')
            print(f"性能数据已导出到 {excel_file}")
            return True
            
        except Exception as e:
            print(f"导出性能数据到Excel时出错: {str(e)}")
            return False


# 创建全局性能日志记录器实例
performance_logger = PerformanceLogger()