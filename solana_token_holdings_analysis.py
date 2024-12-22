# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Dict, List

import pandas as pd
import requests


class SolanaTokenAnalyzer:

    def __init__(self):
        self.rpc_url = "https://api.mainnet-beta.solana.com"  # NOTE: 可以更换为其他接入性能更佳的 RPC 节点
        self.headers = {
            "Content-Type": "application/json"
        }
        
    def _make_rpc_request(self, method: str, params: List) -> Dict:
        """
        发送 RPC 请求到 Solana 节点
        """
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params
        }
        
        try:
            response = requests.post(self.rpc_url, headers=self.headers, json=payload)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as exc:
            raise Exception(f"RPC 请求失败: {str(exc)}")

    def get_token_accounts(self, mint_address: str, limit: int = 100) -> pd.DataFrame:
        """
        获取代币的所有持有账户信息
        
        Parameters:
        mint_address (str): 代币的 mint 地址
        limit (int): 需要获取的持有者数量
        
        Returns:
        pandas.DataFrame: 包含持有者地址和余额的数据框
        """
        method = "getProgramAccounts"
        params = [
            "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",  # Token Program ID
            {
                "encoding": "jsonParsed",
                "filters": [
                    {
                        "dataSize": 165  # Token Account 数据大小
                    },
                    {
                        "memcmp": {
                            "offset": 0,
                            "bytes": mint_address
                        }
                    }
                ]
            }
        ]
        
        try:
            response = self._make_rpc_request(method, params)
            if "result" in response:
                accounts_data = []
                
                for account in response["result"]:
                    parsed_data = account["account"]["data"]["parsed"]["info"]
                    # 只收集非零余额账户
                    if float(parsed_data["tokenAmount"]["amount"]) > 0:
                        accounts_data.append({
                            "address": account["pubkey"],
                            "owner": parsed_data["owner"],
                            "balance": float(parsed_data["tokenAmount"]["amount"]) / (10 ** parsed_data["tokenAmount"]["decimals"]),
                        })

                df = pd.DataFrame(accounts_data)
                # 计算持仓百分比
                total_supply = df['balance'].sum()
                df['percentage'] = (df['balance'] / total_supply * 100).round(4)
                # 按持仓量排序并限制数量
                df = df.sort_values('balance', ascending=False).head(limit)
                df = df.reset_index(drop=True)
                return df
            else:
                raise Exception("API 返回数据格式错误")
        except Exception as exc:
            raise Exception(f"获取账户数据失败: {str(exc)}")

    def analyze_distribution(self, df: pd.DataFrame) -> Dict:
        """
        分析持仓分布情况
        """
        analysis = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_holders': len(df),
            'concentration_metrics': {
                'top_10_percentage': df.head(10)['percentage'].sum(),
                'top_20_percentage': df.head(20)['percentage'].sum(),
                'top_50_percentage': df.head(50)['percentage'].sum(),
            },
            'distribution_ranges': {
                '大户(>10%)': len(df[df['percentage'] > 10]),
                '中户(1-10%)': len(df[(df['percentage'] <= 10) & (df['percentage'] > 1)]),
                '小户(0.1-1%)': len(df[(df['percentage'] <= 1) & (df['percentage'] > 0.1)]),
                '散户(<0.1%)': len(df[df['percentage'] <= 0.1])
            }
        }
        
        return analysis

    def export_results(self, df: pd.DataFrame, analysis: Dict, output_file: str = 'solana_token_analysis.xlsx'):
        """
        导出分析结果到Excel文件
        """
        with pd.ExcelWriter(output_file) as writer:
            # 导出持仓明细
            df.to_excel(writer, sheet_name='持仓明细', index=True)
            
            # 导出分析结果
            analysis_df = pd.DataFrame([
                ['分析时间', analysis['timestamp']],
                ['总持有人数', analysis['total_holders']],
                ['前10持有人占比', f"{analysis['concentration_metrics']['top_10_percentage']:.2f}%"],
                ['前20持有人占比', f"{analysis['concentration_metrics']['top_20_percentage']:.2f}%"],
                ['前50持有人占比', f"{analysis['concentration_metrics']['top_50_percentage']:.2f}%"],
                ['大户数量(>10%)', analysis['distribution_ranges']['大户(>10%)']],
                ['中户数量(1-10%)', analysis['distribution_ranges']['中户(1-10%)']],
                ['小户数量(0.1-1%)', analysis['distribution_ranges']['小户(0.1-1%)']],
                ['散户数量(<0.1%)', analysis['distribution_ranges']['散户(<0.1%)']],
            ], columns=['指标', '数值'])
            
            analysis_df.to_excel(writer, sheet_name='分析摘要', index=False)


def main():
    analyzer = SolanaTokenAnalyzer()
    mint_address = "GxdTh6udNstGmLLk9ztBb6bkrms7oLbrJp5yzUaVpump"

    try:
        # 获取持仓数据
        holders_df = analyzer.get_token_accounts(mint_address)
        # 分析分布情况
        distribution_analysis = analyzer.analyze_distribution(holders_df)
        # 导出结果
        analyzer.export_results(holders_df, distribution_analysis)
        print("分析完成，结果已导出到Excel文件")
    except Exception as exc:
        print(f"分析过程中出现错误: {str(exc)}")


if __name__ == "__main__":
    main()
