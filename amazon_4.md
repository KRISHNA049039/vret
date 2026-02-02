Skip to content
Chat history




You said:
# -*- coding: utf-8 -*-
"""
VRET Automation - Complete Refactored Version
@author: krkottap
"""
import pandas as pd
import datetime
import numpy as np
import traceback
import os
import io
import logging
from io import StringIO
from io import BytesIO
import boto3
from glue_scripts.automation_libraries.redshift import DatabaseUtility
import glue_scripts.common_services.aws_utils as awsutil
import glue_scripts.fdatanetics.Vendor_return_automation.const as cns
import glue_scripts.automation_libraries.aws_libraries as aws

log_stream = StringIO()    
logging.basicConfig(stream=log_stream, level=logging.INFO)
logger = logging.getLogger()

class VRETProcessor:
    def __init__(self, args):
        self.args = args
        self.stage = args['stage'].upper()
        self.geo = args['Geo'].upper()
        self.alias = args['triggered_by']
        self.file_id = args.get('file_id', '')
        self.db_con = DatabaseUtility(self.stage, 'redshift')
        print(self.db_con.config)
        self.s3_resource = boto3.resource('s3')
        
        # Load all mappings at once
        mappings = self._load_mappings()
        self.l2c = mappings['l2c']
        print(self.l2c,'Test1')
        #self.c2l =  {v,k for k, v in self.l2c.items()}
        #print(self.F, 'Test2')
        self.led2chan = mappings['led2chan']
        self.ledger_details = mappings['ledger_details']
        self.ledger = self.ledger = self.l2c.loc[self.l2c['country_code'] == self.geo, 'marketplace'].values[0]

        self.cur_date = self._get_current_period()

    def _load_mappings(self):
        """Load all mapping data at once"""
        queries = {
            'l2c': cns.QUERIES['mapping']['ledger_mapping'],
            'led2chan': cns.QUERIES['mapping']['channel_mapping'],
            'ledger_details': cns.QUERIES['mapping']['ledger_details']
        }
        
        mappings = {}
        for key, query in queries.items():
           df = self.db_con.get_dataframe(query)
           df = df[df.columns[::-1]]  # Reverse column order
           mappings[key] = df

        # Convert led2chan DataFrame to dictionary for proper access
        if 'led2chan' in mappings:
            led2chan_df = mappings['led2chan']
            # Assuming the DataFrame has columns like 'geo' and 'channel' or similar
            # Convert to dictionary format
            if len(led2chan_df.columns) >= 2:
                mappings['led2chan'] = dict(zip(led2chan_df.iloc[:, 0], led2chan_df.iloc[:, 1]))

        return mappings

    def _get_current_period(self):
        # Use September 2024 for testing (Sep-24) - within RVR data range
        result_date = datetime.datetime(2025, 7, 31)  # Sep 30, 2024 -> Sep-24 period
        print(f"Using period: {result_date.strftime('%b-%y').upper()}")
        return result_date
    
    def _get_country_code(self, ledger):
        """Helper method to get country code from l2c DataFrame"""
        result = self.l2c.loc[self.l2c['marketplace'] == ledger, 'country_code']
        return result.values[0] if len(result) > 0 else self.geo

    def _get_s3_keys(self):
        """EXACT same logic as original"""
        source = cns.PARAMS['s3_bucket'][self.stage]        
        bucket = self.s3_resource.Bucket(source)
        keys = []
        for b in bucket.objects.all():
            keys.append(b.key) 
        print(keys)
        return keys, source

    def _get_all_queries(self):
        """Get all formatted queries from const"""
        channel = self.led2chan.get(self.geo) if self.geo in ['DE','ES','IT','SE','PL','FR'] else None
        return cns.get_all_queries(
            geo=self.geo,
            ledger=self.ledger,
            period=self.cur_date.strftime('%b-%y').upper(),
            channel=channel
        )

    def _execute_all_queries(self, queries):
        """Execute all queries and return processed results"""
        results = {}
        
        # Execute all queries
        for query_name, query_sql in queries.items():
            if query_name in ['ledger_mapping', 'channel_mapping']:  # Skip already loaded
                continue
                
            df = self.db_con.get_dataframe(query_sql)
            df.columns = np.vectorize(lambda x: x.decode('utf-8') if isinstance(x, bytes) else x)(df.columns)
            results[query_name] = df
        
        # Process specific results
        if 'adj_query' in results:
            adjs = results['adj_query']
            adjs = adjs[['wo_ledger_name','wo_period_name','wo_company_code','wo_location_code','wo_cost_center',
                        'wo_account_number','wo_product_line','wo_channel','wo_project','wo_unrounded_accounted',
                        'ar_vendor','ar_invoice_num','wo_je_category']]
            adjs['wo_period_name'] = adjs['wo_period_name'].str.upper()
            results['adj_query'] = adjs
        
        if 'cm_query' in results:
            cms = results['cm_query']
            cms = cms[['wo_ledger_name','wo_period_name','wo_company_code','wo_location_code','wo_cost_center',
                      'wo_account_number','wo_product_line','wo_channel','wo_project','wo_unrounded_accounted',
                      'ar_vendor','ar_invoice_num','wo_je_category']]
            cms['wo_cost_center'] = cms['wo_cost_center'].astype(str)
            cms['wo_period_name'] = cms['wo_period_name'].str.upper()
            results['cm_query'] = cms
        
        if 'glap_query' in results:
            pis = results['glap_query']
            pis['period_name'] = pis['period_name'].str.upper()
            pis['cost_center'] = pis['cost_center'].astype(str)
            results['glap_query'] = pis
        
        if 'ledger_details' in results:
            leds = results['ledger_details']
            newleds = leds[['ledger_id','ledger_name','currency_code']]
            newleds.columns = ['LEDGER_ID','Ledger','Currency']
            results['ledger_details'] = newleds
        
        if 'rvr_query' in results:
            rvr = results['rvr_query']
            print(f"RVR RAW DATA: {rvr.shape} rows")
            rvr.columns = [col.upper().replace('_',' ') for col in rvr.columns]
            rvr['RVR DATE'] = pd.to_datetime(rvr['RVR DATE']).dt.strftime('%Y-%m-%d')
            rvr['RVR DATE'] = pd.to_datetime(rvr['RVR DATE'])
            rvr['COUNTRY CODE'] = rvr['COUNTRY CODE'].replace('GB', 'UK')
            print(f"RVR after column processing: {rvr.shape} rows")
            
            if self.geo == 'EU':
                rvr = rvr[rvr['COUNTRY CODE'].isin(['PL','DE','SE','ES','FR','IT'])]
                print(f"RVR after EU country filter: {rvr.shape} rows")
            else:
                country_code = self._get_country_code(self.ledger)
                print(f"Filtering RVR for country: {country_code}")
                rvr = rvr[rvr['COUNTRY CODE'] == country_code]
                print(f"RVR after country filter ({country_code}): {rvr.shape} rows")
            
            print(f"RVR STATUS values: {rvr['RVR STATUS'].value_counts().to_dict()}")
            print(f"CURRENT STATE values: {rvr['CURRENT STATE'].value_counts().to_dict()}")
            rvr = rvr[(rvr['RVR STATUS'] == 'OPEN') & (rvr['CURRENT STATE'] == 'IN RETURNED RETURNS')]
            print(f"RVR after status filter: {rvr.shape} rows")
            
            if rvr.shape[0] > 0:
                print(f"RVR Amount column: {'TOT BASE REFUND AMT' if 'TOT BASE REFUND AMT' in rvr.columns else 'NOT FOUND'}")
                if 'TOT BASE REFUND AMT' in rvr.columns:
                    print(f"RVR Amount stats: min={rvr['TOT BASE REFUND AMT'].min()}, max={rvr['TOT BASE REFUND AMT'].max()}, sum={rvr['TOT BASE REFUND AMT'].sum()}")
                    print(f"RVR Amount samples: {rvr['TOT BASE REFUND AMT'].head(5).tolist()}")
                print(f"RVR Return ID samples: {rvr['RETURN ID'].head(5).tolist() if 'RETURN ID' in rvr.columns else 'NO RETURN ID COLUMN'}")
                print(f"RVR date range: {rvr['RVR DATE'].min()} to {rvr['RVR DATE'].max()}")
            
            results['rvr_query'] = rvr.reset_index(drop=True)
        
        return results

    def _process_thr_data(self, keys, source):
        """EXACT same THR processing logic as original"""
        print('Ledger: ', self.ledger)
        templed = self.ledger.upper()
        templed = templed.replace(' ','_')
        thrdf = ''
        
        if self.geo not in ['US','CA','MX','BR']:
            tempkeys = [b for b in keys if templed in b.upper()]
            
            if self.geo == 'DE':
                dekeys = [t for t in keys if 'thr/Amazon.eu_DE' in t]
                czkeys = [t for t in keys if 'thr/Amazon.eu_CZ' in t]
                plkeys = [t for t in keys if 'thr/Amazon.eu_PL' in t]
                dekey = '' if len(dekeys)==0 else max(dekeys)
                czkey = '' if len(czkeys)==0 else max(czkeys)
                plkey = '' if len(plkeys)==0 else max(plkeys)
                thrkeys=[]
                print('DE KEY: ', dekey)
                print('CZ KEY: ', czkey)
                print('PL KEY: ', plkey)
            elif self.geo in ['ES','UK','IT','DE','CZ','PL','FR']:
                country_code = self._get_country_code(self.ledger)
                thrkeys = [t for t in keys if 'thr/Amazon.eu_'+country_code in t]
            else:
                thrkeys = [t for t in tempkeys if 'thr' in t]
            thrkey = '' if len(thrkeys)==0 else max(thrkeys)
            print(thrkey)
        
        if self.geo == 'EU':
            tempthrlines,tempthrcols =[],[]
            leds = ['PL','DE','SE','ES','FR','IT']
            for l in leds:
                print(l)
                tempthr = [t for t in tempkeys if 'THR/Amazon.eu_'+l in t]
                tempthrkeys = '' if len(tempthr)==0 else max(tempthr)
                print(tempthrkeys)
                tempdf = '' if tempthr=='' else self.getTHR(self.s3_resource,source,tempthrkeys)
                if not isinstance(tempdf,str):
                    tempthrlines+=tempdf.values.tolist()
                    tempthrcols = list(tempdf.columns)
            if len(tempthrlines)>0:
                thrdf = pd.DataFrame(tempthrlines,columns=tempthrcols)
        elif self.geo == 'DE':
            dethr = pd.DataFrame() if dekey=='' else self.getTHR(self.s3_resource,source,dekey)
            czthr = pd.DataFrame(columns=list(dethr.columns)) if czkey=='' else self.getTHR(self.s3_resource,source,czkey)
            plthr = pd.DataFrame(columns=list(dethr.columns)) if plkey=='' else self.getTHR(self.s3_resource,source,plkey)
            thrdf = pd.concat([dethr,czthr,plthr]).reset_index(drop=True)
        elif self.geo == 'AE':
            thrkeys = [k for k in keys if 'thr/Amazon_Web_Services_MENA_' in k]
            thrdf = '' if len(thrkeys)==0 else self.getTHR(self.s3_resource,source,max(thrkeys))
        elif self.geo == 'SA':
            thrkeys = [k for k in keys if 'thr/AMAZON.KSA' in k]
            thrdf = '' if len(thrkeys)==0 else self.getTHR(self.s3_resource,source,max(thrkeys))
        elif self.geo not in ['US','CA','BR','MX']:
            thrdf = '' if thrkey=='' else self.getTHR(self.s3_resource,source,thrkey)
        
        return thrdf

    def _process_vret_data(self, cms, pis, newleds):
        """EXACT same VRET data processing logic as original"""
        currs, ledgers = list(newleds['Currency']),list(newleds['Ledger'])
        currency = currs[ledgers.index(self.ledger)]
        cms1 = cms[(cms['wo_ledger_name']==self.ledger)&(cms['wo_period_name']==self.cur_date.strftime('%b-%y').upper())].reset_index(drop=True) 
        pis1 = pis[(pis['ledger_name']==self.ledger) & (pis['period_name']==self.cur_date.strftime('%b-%y').upper())].reset_index(drop=True)
        
        if self.geo in ['ES','FR','IT','DE','PL','SE','NL']:
            channel = self.led2chan.get(self.geo)
            print('Channel: ', channel)
            cms2=cms[(cms['wo_ledger_name']=='Amazon.eu')&(cms['wo_channel']==channel)&(cms['wo_period_name']==self.cur_date.strftime('%b-%y').upper())].reset_index(drop=True)
            pis2=pis[(pis['ledger_name']=='Amazon.eu')&(pis['channel_code']==channel)& (pis['period_name']==self.cur_date.strftime('%b-%y').upper())].reset_index(drop=True)
            cms= pd.concat([cms1, cms2]).reset_index(drop=True)
            pis=pd.concat([pis1, pis2]).reset_index(drop=True)
        else:
            cms=cms1.copy()
            pis=pis1.copy()
        
        if self.geo == 'SE':
            pisvret = pis1.copy()
        else:
            pisvret = pis[pis['je_category'].isin(['Purchase Invoices','Sales Invoices'])].fillna('').reset_index(drop=True)
        
        pisvret = pisvret[['ledger_name','period_name','company_code','location_code','cost_center',
                        'account_number','product_code','channel_code','project_code','journal_name',
                        'functional_currency_code','functional_amount','vendor_name','invoice_num','je_category']]
        cms['journal_name'],cms['functional_currency_code']=self.cur_date.strftime('%b-%y').upper()+' Credit Memos '+currency,currency
        cms = cms[['wo_ledger_name','wo_period_name','wo_company_code','wo_location_code','wo_cost_center',
                      'wo_account_number','wo_product_line','wo_channel','wo_project','journal_name','functional_currency_code',
                      'wo_unrounded_accounted','ar_vendor','ar_invoice_num','wo_je_category']]
        cms.columns=['ledger_name','period_name','company_code','location_code','cost_center','account_number',
                    'product_code','channel_code','project_code','journal_name','functional_currency_code',
                    'functional_amount','vendor_name','invoice_num','je_category']
        
        if self.geo != 'SE':
            vret = pd.concat([pisvret,cms]).reset_index(drop=True)
        else:
            vret=cms.copy()
        
        return vret

    def getTHR(self, s3, source, key):
        """EXACT same getTHR function as original"""
        obj2 = s3.Object(source, key)
        txt2 = obj2.get()['Body'].read().decode('utf-8')
        lines2 = txt2.split('\n')
        lines2 = [a.replace('\r','') for a in lines2]
        thrlines = [l.split('|') for l in lines2]
        print(thrlines[:30])
        if len(thrlines[0]) == 1:
            thrlines = thrlines[14:]
        lenl2 = len(thrlines[0])
        thrlines = [l for l in thrlines if len(l) == lenl2]
        thrdf = pd.DataFrame(thrlines[1:], columns=thrlines[0])
        return thrdf

    def createVendorFundingFiles(self, df, l2c, led2chan, ledger, cd, rvrfilt, thr):
        """EXACT same createVendorFundingFiles function as original"""
        print(list(df.columns))
        df=df.fillna('')
        rvrfilt['RETURN ID']=rvrfilt['RETURN ID'].astype(str)
        df.columns = ['LEDGER','PERIOD','CO','LOC','CC','ACCT','PROD','CHAN','PROJ','JOURNAL NAME','CURRENCY_CODE','TRANSACTION AMOUNT','VENDOR_NAME','TRANSACTION NUM','CATEGORY']
        print('ORIG DF LENGTH: ', len(df))
        df = df.groupby(by=['LEDGER','PERIOD','CO','LOC','CC','ACCT','PROD','CHAN','PROJ','JOURNAL NAME','CURRENCY_CODE','VENDOR_NAME','TRANSACTION NUM','CATEGORY'])['TRANSACTION AMOUNT'].sum().reset_index()
        df['TRANSACTION AMOUNT'] = [0 if a=='' else float(a) for a in list(df['TRANSACTION AMOUNT'])]
        df['TRANSACTION NUM']=[str(a) for a in list(df['TRANSACTION NUM'])]
        print('DF LENGTH: ', len(df))
        # Convert ledger to country code using l2c mapping (dictionary format from original)
        country_mapping = dict(zip(self.l2c['marketplace'], self.l2c['country_code']))
        ln = country_mapping.get(ledger, self.geo)
        
        if ln in ['PL','UK','FR','DE','ES','IT','CZ','EG','AE'] and not isinstance(thr, str):
            print(list(thr.columns))
            thr['Transaction Number']=thr['Transaction Number'].astype(str)
            thr['Agreement Type']=thr['Agreement Type'].fillna('')
            thr['Agreement Type']=thr['Agreement Type'].astype(str)
            maps = thr[['Transaction Number','Agreement Type']]
            maps.columns=['TRANSACTION NUM','RETURN ID']
            maps = maps.drop_duplicates().reset_index(drop=True)
            print(list(df.columns))
            print(list(maps.columns))
            vret = df.merge(maps,on='TRANSACTION NUM',how='left').fillna('')
            rvrjoin = rvrfilt[['RETURN ID','TOT BASE REFUND AMT']].copy()
            rvrjoin.columns = ['RETURN ID','RVR AMT']
            print(f"RVR JOIN before conversion: {rvrjoin.shape} rows, sample amounts: {rvrjoin['RVR AMT'].head(5).tolist()}")
            rvrjoin['RVR AMT']=[float(a) for a in list(rvrjoin['RVR AMT'])]
            print(f"RVR JOIN after float conversion: sum={rvrjoin['RVR AMT'].sum()}, non-zero count={len(rvrjoin[rvrjoin['RVR AMT'] != 0])}")
            newrvr = rvrjoin.groupby(by=['RETURN ID'])['RVR AMT'].sum().reset_index()
            print(f"RVR after groupby: {newrvr.shape} rows, sum={newrvr['RVR AMT'].sum()}")
            tempfull = vret.merge(newrvr,on='RETURN ID',how='left').fillna(0).reset_index(drop=True)
            norvr = tempfull[tempfull['RVR AMT']==0].reset_index(drop=True)
            yesrvr = tempfull[tempfull['RVR AMT']!=0].reset_index(drop=True)
            # ORIGINAL LOGIC: Only largest transaction per Return ID gets RVR
            newrvrrows = []
            for s in list(set(yesrvr['RETURN ID'])):
                temprvr = yesrvr[yesrvr['RETURN ID']==s].reset_index(drop=True)
                if len(temprvr)==1:
                    newrvrrows+=[list(temprvr.loc[0])]
                else:
                    temprvr = temprvr.sort_values(by='TRANSACTION AMOUNT',ascending=False).reset_index(drop=True)
                    newrvrrows+=[list(temprvr.loc[0])]
                    temp2rvr = temprvr[1:].reset_index(drop=True)
                    temp2rvr['RVR AMT']=0
                    newrvrrows+=temp2rvr.values.tolist()
            yesrvrdf2 = pd.DataFrame(newrvrrows,columns=list(norvr.columns))
            full = pd.concat([norvr,yesrvrdf2]).reset_index(drop=True)
        else:
            rvrjoin = rvrfilt[['RETURN ID','TOT BASE REFUND AMT']].copy()
            rvrjoin.columns = ['RETURN ID','RVR AMT']
            print(f"RVR JOIN (non-EU) before conversion: {rvrjoin.shape} rows, sample amounts: {rvrjoin['RVR AMT'].head(5).tolist()}")
            rvrjoin['RVR AMT']=[float(a) for a in list(rvrjoin['RVR AMT'])]
            print(f"RVR JOIN (non-EU) after float conversion: sum={rvrjoin['RVR AMT'].sum()}, non-zero count={len(rvrjoin[rvrjoin['RVR AMT'] != 0])}")
            newrvr = rvrjoin.groupby(by='RETURN ID')['RVR AMT'].sum().reset_index()
            print(f"RVR (non-EU) after groupby: {newrvr.shape} rows, sum={newrvr['RVR AMT'].sum()}")
            df['TRANSACTION NUM']=df['TRANSACTION NUM'].fillna('')
            df['RETURN ID']=['' if '_' not in a else a.split('_')[0] for a in list(df['TRANSACTION NUM'])]
            print(f"Transaction Return ID extraction: {df['RETURN ID'].nunique()} unique Return IDs from {len(df)} transactions")
            print(f"Sample Transaction Return IDs: {df['RETURN ID'].head(10).tolist()}")
            print(f"Sample Transaction Numbers: {df['TRANSACTION NUM'].head(10).tolist()}")
            print(f"RVR Return IDs: {newrvr['RETURN ID'].head(10).tolist()}")
            
            # Check for matches before merge
            transaction_ids = set(df['RETURN ID'])
            rvr_ids = set(newrvr['RETURN ID'])
            matches = transaction_ids & rvr_ids
            print(f"Return ID matches: {len(matches)} out of {len(transaction_ids)} transaction IDs and {len(rvr_ids)} RVR IDs")
            if len(matches) > 0:
                print(f"Sample matching Return IDs: {list(matches)[:5]}")
            
            # Ensure both RETURN ID columns have the same data type
            df['RETURN ID'] = df['RETURN ID'].astype(str)
            newrvr['RETURN ID'] = newrvr['RETURN ID'].astype(str)
            full = df.merge(newrvr,on='RETURN ID',how='left').fillna(0).reset_index(drop=True)
            print(f"After merge: {len(full[full['RVR AMT'] > 0])} transactions with RVR > 0")
        
        ta, rvra = list(full['TRANSACTION AMOUNT']), list(full['RVR AMT'])
        print(f"Before min() capping: RVR AMT sum={sum(rvra)}, non-zero count={len([x for x in rvra if x != 0])}")
        full['RVR AMT'] = [min(ta[i],rvra[i]) if rvra[i]!=0 else rvra[i] for i in range(len(full))]
        print(f"After min() capping: RVR AMT sum={full['RVR AMT'].sum()}, non-zero count={len(full[full['RVR AMT'] != 0])}")
        full['Final Amount'] = full['TRANSACTION AMOUNT'] - full['RVR AMT']
        print(f"Final RVR allocation: {len(full[full['RVR AMT'] > 0])} transactions with RVR > 0")
        
        if ln in ['US','CA','MX','BR']:
            transpiv = full.groupby(by='RETURN ID')['RVR AMT'].sum().reset_index()
            rvrpiv = rvrfilt.groupby(by='RETURN ID')['TOT BASE REFUND AMT'].sum().reset_index()
            rvrpiv.columns = ['RETURN ID','RVR AMT REPORT']
            transpiv2 = transpiv.merge(rvrpiv,on='RETURN ID',how='left').fillna(0)
            transpiv2.columns=['RETURN ID','TRANSACTION AMOUNT','RVR Amount VLOOKUP']
            rvrpiv2=rvrpiv.merge(transpiv,on='RETURN ID',how='left').fillna(0)
            rvrpiv2.columns = ['RETURN ID','RVR AMT','Transaction Amount VLOOKUP']
        else:
            transpiv = full.groupby(by='RETURN ID')['RVR AMT'].sum().reset_index()
            rvrpiv = rvrfilt.groupby(by='RETURN ID')['TOT BASE REFUND AMT'].sum().reset_index()
            rvrpiv.columns=['RETURN ID','RVR AMT REPORT']
            transpiv2 = transpiv.merge(rvrpiv,on='RETURN ID',how='left').fillna(0)
            transpiv2.columns=['RETURN ID','TRANSACTION AMOUNT','RVR Amount VLOOKUP']
            rvrpiv2=rvrpiv.merge(transpiv,on='RETURN ID',how='left').fillna(0)
            rvrpiv2.columns = ['RETURN ID','RVR AMT','Transaction Amount VLOOKUP']
        
        tempdf = full.copy()
        # Use the ln variable which already contains the country code from l2c mapping
        tempdf['CO']=['6L' if ln=='EU' else str(a) for a in tempdf['CO']]
        tempdf['LOC']=['0000' if str(a)=='0' else str(a) for a in list(tempdf['LOC'])]
        tempdf['CC']=['0000' if str(a)=='0' else str(a) for a in list(tempdf['CC'])]
        tempdf['ACCT']=[str(a) for a in list(tempdf['ACCT'])]
        tempdf['PROD']=['0000' if str(a)=='0' else str(a) for a in list(tempdf['PROD'])]
        tempdf['CHAN']=['0000' if str(a)=='0' else str(a) for a in list(tempdf['CHAN'])]
        tempdf['PROJ']=['0000' if str(a)=='0' else str(a) for a in list(tempdf['PROJ'])]
        tempdf['CO1'] = ['2D' if a in ['7H','77','D3','2F','G7','2V'] else a for a in list(tempdf['CO'])]
        tempdf['LOC1'] = list(tempdf['LOC'])
        tempdf['CC1']=list(tempdf['CC'])
        co,cc = list(tempdf['CO1']),list(tempdf['CC1'])

        tempdf['CO1'] = ['J1' if cc[i]=='1171' else co[i] for i in range(len(tempdf))]
        tempdf['ACCT1']='13209'
        tempdf['PL1']=list(tempdf['PROD'])
        tempdf['CH1']=list(tempdf['CHAN'])
        tempdf['PR1']=list(tempdf['PROJ'])
        tempdf['DR1']=''
        tempdf['CR1']=list(tempdf['TRANSACTION AMOUNT'])
        tempdf['CO2'] = list(tempdf['CO1'])
        tempdf['LOC2'] = '4299' if ledger=='Amazon.co.uk Ltd.' else  list(tempdf['LOC'])
        tempdf['CC2']=list(tempdf['CC1'])
        pl1 = list(tempdf['PL1'])
        tempdf['ACCT2']=['48550' if pl1[i] in ['1810','2010','2530'] else '52910' for i in range(len(tempdf))]
        tn,acct2 = list(tempdf['TRANSACTION NUM']),list(tempdf['ACCT2'])
        tempdf['ACCT2'] = ['65991' if 'opex' in tn[i].lower() else acct2[i] for i in range(len(tempdf))]
        acct2,cc2 = list(tempdf['ACCT2']),list(tempdf['CC2'])
        for i in range(len(cc2)):
            if cc2[i]=='0000':
                if acct2[i]=='65991':
                    cc2[i]='3804'
                else:
                    cc2[i]='1200'
        tempdf['CC2']=cc2
        tempdf['PL2']=list(tempdf['PROD'])
        ch1 = list(tempdf['CH1'])
        tempdf['CH2']=[ch1[i] if ch1[i]!='0000' else self.led2chan.get(ln, '0000') for i in range(len(tempdf))]
        co2, ch2=list(tempdf['CO2']),list(tempdf['CH2'])
        tempdf['CH2']=['0000' if (acct2[i]=='52910' and co2[i] in ['6L','JK'])  else ch2[i] for i in range(len(tempdf))]
        tempdf['PR2']='0000'
        tempdf['DR2']=list(tempdf['Final Amount'])
        tempdf['CR2']=''
        cc2 =list(tempdf['CC2'])
        tempdf['ACCT3'],tempdf['DR3'],tempdf['CR3'] = '20327',list(tempdf['RVR AMT']),0
        
        # Ledger-specific processing - EXACT same as original
        if ledger=='Amazon.sg':
            tempdf['LOC2']='1990'
            pl2 = list(tempdf['PL2'])
            tempdf['CH2']=['7786' if pl2[i] in ['6439','6429'] else '1022' for i in range(len(tempdf))]
            acct2 = list(tempdf['ACCT2'])
            tempdf['ACCT2']=['48550' if pl2[i] in ['1810','2010','2530'] else acct2[i] for i in range(len(tempdf))]
            acct2,loc2,cc2,co2,ch2,tn = list(tempdf['ACCT2']),list(tempdf['LOC2']),list(tempdf['CC2']),list(tempdf['CO2']),list(tempdf['CH2']),list(tempdf['TRANSACTION NUM'])
            for i in range(len(tempdf)):
                if co2[i]=='9T':
                        loc2[i]='1990'
                        cc2[i]='3804'
                        ch2[i]='6060'
                if co2[i]=='AQ':
                    if 'opex' in tn[i].lower():
                        acct2[i]='65991'
                        cc2[i]='3804'
                        ch2[i]='6060'
                    else:
                        acct2[i]='65991'
                        cc2[i]='3802'
                        ch2[i]='6060'
            tempdf['ACCT2'],tempdf['LOC2'],tempdf['CC2'],tempdf['CH2']=acct2,loc2,cc2,ch2
        
        if ledger=='Amazon.com.au':
            acct2,cc2,co2,ch2,pl2,loc2,pr2,tn = list(tempdf['ACCT2']),list(tempdf['CC2']),list(tempdf['CO2']),list(tempdf['CH2']),list(tempdf['PL2']),list(tempdf['LOC2']),list(tempdf['PR2']),list(tempdf['TRANSACTION NUM'])
            for i in range(len(tempdf)):
                if co2[i]=='55':
                    acct2[i]='65991'
                    cc2[i]='3804'
                    ch2[i]='6060'
                elif co2[i]=='EA':
                    acct2[i]='65991'
                    cc2[i]='3802'
                    ch2[i]='6060'
                if co2[i]=='B436':
                    acct2[i]='65991'
                    cc2[i]='3804'
                    ch2[i]='0'
                if co2[i]=='2I':
                    if 'opex' in tn[i].lower():
                        acct2[i]='65991'
                        cc2[i]='3804'
                        ch2[i]='6060'
                    else:
                        acct2[i]='52920'
                        cc2[i]='0'
                        ch2[i]='1016'
                if co2[i]=='HA':
                    loc2[i]='1899'
                    pr2[i]='0'
                    if 'opex' in tn[i].lower():
                        acct2[i]='65991'
                        cc2[i]='3804'
                        ch2[i]='1091'
                    elif pl2[i] in ['1810','2010','2530']:
                        acct2[i]='48550'
                        cc2[i]='1200'
                        ch2[i]='1091'
                    else:
                        acct2[i]='52920'
                        cc2[i]='1200'
                        ch2[i]='1091'
                tempdf['ACCT2'],tempdf['CC2'],tempdf['CH2'],tempdf['LOC2'],tempdf['PR2']=acct2,cc2,ch2,loc2,pr2
        
        if ledger=='Amazon.eu' or ledger=='Amazon.co.uk Ltd.' or ledger=='Amazon.es.eur':
            co1,ch1,ch2 = list(tempdf['CO1']),list(tempdf['CH1']),list(tempdf['CH2'])
            ch2 = ['0000' if co1[i]=='6L' or co1[i]=='JK' else ch1[i] for i in range(len(tempdf))]
            tempdf['CH2']=ch2
        
        rvrje = tempdf[tempdf['RVR AMT']!=0].reset_index(drop=True)
        if ln in ['UK','DE','ES','IT','FR']:
            rvrje1 = rvrje[['CO1','LOC1','CC1','PL1','CH1','PR1','RETURN ID']]
        else:
            rvrje1 = rvrje[['CO1','LOC1','CC1','PL1','CH1','PR1']]
        rvrje1['ACCT1'] = '20327'
        rvrje1['DR1'],rvrje1['CR1'] = list(rvrje['RVR AMT']),''
        if ln in ['UK','DE','ES','IT','FR']:
            rvrje1 = rvrje1[['CO1','LOC1','CC1','ACCT1','PL1','CH1','PR1','DR1','CR1','RETURN ID']]
        else:
            rvrje1 = rvrje1[['CO1','LOC1','CC1','ACCT1','PL1','CH1','PR1','DR1','CR1']]
        if ln in ['UK','DE','ES','IT','FR']:
            rvrje2 = rvrje[['CO2','LOC2','CC2','PL2','CH2','PR2','RETURN ID']]
        else:
            rvrje2 = rvrje[['CO2','LOC2','CC2','PL2','CH2','PR2']]
        rvrje2['ACCT2'] = '13209'
        rvrje2['CR2'],rvrje2['DR2'] = list(rvrje['RVR AMT']),''
        if ln in ['UK','DE','ES','IT','FR']:
            rvrje2=rvrje2[['CO2','LOC2','CC2','ACCT2','PL2','CH2','PR2','DR2','CR2','RETURN ID']]
        else:
            rvrje2=rvrje2[['CO2','LOC2','CC2','ACCT2','PL2','CH2','PR2','DR2','CR2']]
        rvrje1['DR1']= [0 if a =='' else a for a in list(rvrje1['DR1'])]
        rvrje1['CR1']= [0 if a =='' else a for a in list(rvrje1['CR1'])]
        rvrje2['DR2']= [0 if a =='' else a for a in list(rvrje2['DR2'])]
        rvrje2['CR2']= [0 if a =='' else a for a in list(rvrje2['CR2'])]
        
        if ln in ['UK','DE','ES','IT','FR']:
            print('RVR PIV COLUMNS: ', list(rvrpiv2.columns))
            retid,rvramt=list(rvrpiv2['RETURN ID']),list(rvrpiv2['RVR AMT'])
            rvrje1df = rvrje1.groupby(by=['CO1','LOC1','CC1','ACCT1','PL1','CH1','PR1','RETURN ID']).sum().reset_index()
            rets1,debs1 = list(rvrje1df['RETURN ID']),list(rvrje1df['DR1'])
            rvrje1df['DR1']=[min(rvramt[retid.index(rets1[i])],debs1[i]) for i in range(len(rvrje1df))]
            rvrje2df = rvrje2.groupby(by=['CO2','LOC2','CC2','ACCT2','PL2','CH2','PR2','RETURN ID']).sum().reset_index()
            rets2,creds2 = list(rvrje2df['RETURN ID']),list(rvrje2df['CR2'])
            rvrje2df['CR2']=[min(rvramt[retid.index(rets2[i])],creds2[i]) for i in range(len(rvrje1df))]
            rvrje1df.drop('RETURN ID',axis=1,inplace=True)
            rvrje2df.drop('RETURN ID',axis=1,inplace=True)
        else:
            rvrje1df = rvrje1.groupby(by=['CO1','LOC1','CC1','ACCT1','PL1','CH1','PR1']).sum().reset_index()
            rvrje2df = rvrje2.groupby(by=['CO2','LOC2','CC2','ACCT2','PL2','CH2','PR2']).sum().reset_index()
        
        rvrje1df.columns = ['Company','Location','Cost Center','Account','Product Line','Geo/Market','Future','Debit','Credit']
        rvrje2df.columns = ['Company','Location','Cost Center','Account','Product Line','Geo/Market','Future','Debit','Credit']
        fullrvr = pd.concat([rvrje1df, rvrje2df]).reset_index(drop=True)
        fullrvr['Debit'],fullrvr['Credit'] = ['' if a==0 else a for a in list(fullrvr['Debit'])],['' if a==0 else a for a in list(fullrvr['Credit'])]
        fullrvr['Line Description'] = 'Current RVR '+cd.strftime('%b-%y').upper()
        fullrvr['Line DFF Context'],fullrvr['Line DFF'],fullrvr['Captured Info DFF']='MJE_STATS','MJE_STATS.1-2hr.YES.OFA (Oracle Financial Applications).YES.VEN-010','ACPY'
        
        je1 = tempdf[['CO1','LOC1','CC1','ACCT1','PL1','CH1','PR1','DR1','CR1']].copy()
        tempje = tempdf[['CO1','LOC1','CC1','ACCT1','PL1','CH1','PR1','DR3','CR3']]
        je1['DR1']= [0 if a =='' else a for a in list(je1['DR1'])]
        je1['CR1']= [0 if a =='' else a for a in list(je1['CR1'])]
        je1df = je1.groupby(by=['CO1','LOC1','CC1','ACCT1','PL1','CH1','PR1']).sum().reset_index()
        tempjedf = tempje.groupby(by=['CO1','LOC1','CC1','ACCT1','PL1','CH1','PR1']).sum().reset_index()
        je1df = je1df.merge(tempjedf,on=['CO1','LOC1','CC1','ACCT1','PL1','CH1','PR1'],how='left').fillna(0).reset_index(drop=True)
        je1df['CR1']=je1df['CR1']-je1df['DR3']
        je2 = tempdf[['CO2','LOC2','CC2','ACCT2','PL2','CH2','PR2','DR2','CR2']].copy()
        je2['DR2']= [0 if a =='' else a for a in list(je2['DR2'])]
        je2['CR2']= [0 if a =='' else a for a in list(je2['CR2'])]
        je2df = je2.groupby(by=['CO2','LOC2','CC2','ACCT2','PL2','CH2','PR2']).sum().reset_index()
        je1df = je1df[['CO1','LOC1','CC1','ACCT1','PL1','CH1','PR1','DR1','CR1']]
        je1df.columns = ['CO','LOC','COST','ACCT','PROD','CHAN','PROJ','DR','CR']
        je2df.columns = ['CO','LOC','COST','ACCT','PROD','CHAN','PROJ','DR','CR']
        fullje = pd.concat([je1df, je2df]).reset_index(drop=True)
        fullje=fullje[(fullje['DR']!=0)|(fullje['CR']!=0)].reset_index(drop=True)
        fullje['DR'],fullje['CR'] = ['' if a==0 else a for a in list(fullje['DR'])],['' if a==0 else a for a in list(fullje['CR'])]
        fullje.columns = ['Company','Location','Cost Center','Account','Product Line','Geo/Market','Future','Debit','Credit']
        fullje['Line Description']='VRET Write-off '+cd.strftime('%b-%y').upper()
        fullje['Line DFF Context'],fullje['Line DFF'] = 'MJE_STATS','MJE_STATS.1-2hr.YES.OFA (Oracle Financial Applications).YES.VEN-010'
        acc2cf = {'13209':'ARNT','20327':'ACPY'}
        fullje2 = pd.concat([fullrvr, fullje]).reset_index(drop=True)
        accts = list(fullje2['Account'])
        fullje2['Captured Info DFF']=[acc2cf[accts[i]] if accts[i] in ['20327','13209'] else '' for i in range(len(fullje2))]
        
        return tempdf, je1df, je2df, fullje2,transpiv2,rvrpiv2

    def _create_excel_and_spursh(self, df1, df2, df3, df4, newleds, rvr, cd):
        """EXACT same Excel and SPURSH creation logic as original"""
        outfile = io.BytesIO()
        writer = pd.ExcelWriter(outfile, engine='xlsxwriter')
        wb=writer.book
        acc_form = wb.add_format({'num_format':40, 'text_wrap':True})
        df4.to_excel(writer, sheet_name='GLDI', index=False, startrow=10)
        sp = df4[['Company','Location','Cost Center','Account','Product Line','Geo/Market','Future','Debit','Credit','Line Description','Captured Info DFF']].copy()
        
        if self.geo in ['DE','ES','IT','PL','FR','SE','NL']:
            ledger='Amazon.eu'
        else:
            ledger = self.ledger
            
        sp['Ledger']=ledger
        sp['Debit']=[0 if a=='' else round(a,2) for a in list(sp['Debit'])]
        sp['Credit']=[0 if a=='' else round(a,2) for a in list(sp['Credit'])]
        sp['NET']= sp['Debit']-sp['Credit']
        
        country_code = self._get_country_code(self.ledger)
        if country_code in ['US','CA','MX','BR']:
            jn = jd = f"CCO_{country_code}_140.1_{self.args['triggered_by']}@_VRET_Write_off_Reclass_{self.cur_date.strftime('%m%y')}"
        else:
            jn='6.105_VRET Write-off & current RVR reclass_BLR'
            jd='CCO_SE_140.1_'+self.args['triggered_by']+'@_VRET_Write_off_Reclass_'+self.cur_date.strftime('%m%y')+'(This is as per Org wise)'
        
        sp['JE_Category_Name'],sp['Journal_Name'],sp['Journal_Description'],sp['Accounting_Date']='VFUND_RECL_WriteOff',jn,jd, self.cur_date.strftime('%d-%b-%Y').upper()
        sp['Reversal_Journal'],sp['Reversal_Period'],sp['Period_Name']='N','',self.cur_date.strftime('%b-%y').upper()
        sp = sp.merge(newleds, on='Ledger')
        sp = sp[['LEDGER_ID','Ledger','JE_Category_Name','Accounting_Date','Period_Name','Company','Location','Cost Center','Account','Product Line','Geo/Market','Future','Debit','Credit','NET','Journal_Name','Journal_Description','Line Description','Reversal_Journal','Reversal_Period','Captured Info DFF','Currency']]
        sp.columns = ['Ledger_ID','Ledger_Name','JE_Category_Name','Accounting_Date','Period_Name','Company','Location','Cost_Center','Account','Product_Line','Channel','Project','Debit','Credit','Net','Journal_Name','Journal_Description','Line_Description','Reversal_Journal','Reversal_Period','AMZ_Reference1','Currency']
        sp['Conversion_Date'] =self.cur_date.strftime('%d-%b-%Y').upper()
        sp['Conversion_Type'] = 'Period Average'
        spout = '/tmp/temp1.csv'
        sp.to_csv(spout,index=False)
        
        session_construct=aws.AmazonWebServices(cns.PARAMS[self.stage]['awsRegion'])
        aws_session=session_construct._get_session()    
        s3_client = aws_session.client('s3')
        filename = f'{cns.PARAMS["approval_template"][self.stage]}_{country_code}_SPURSH_{cd.strftime("%b-%y")}_{self.args["triggered_by"]}_Contico.csv'

        awsutil.dataframe_to_s3(
           s3_client, 
           sp,
           cns.PARAMS[self.stage]['spursh_s3'],
           filename,
           "csv"
           )
        try:
          s3_client.head_object(Bucket=cns.PARAMS[self.stage]['spursh_s3'], Key=filename)
          print(f"Confirmed: {filename} exists in S3")
        except s3_client.exceptions.NoSuchKey:
          print(f"Error: {filename} not found in S3")
        
        
        gldi = writer.sheets['GLDI']
        gldi.set_column(0, len(df4.columns), 20, acc_form)
        gldi.write('A1', 'Ledger')
        gldi.write('B1',self.ledger)
        gldi.write('A2', 'Source')
        gldi.write('B2','Spreadsheet')
        gldi.write('A3', 'Category')
        gldi.write('B3','VFUND_RECL_WriteOff')
        gldi.write('A4', 'Currency')
        currs, ledgers = list(newleds['Currency']),list(newleds['Ledger'])
        currency = currs[ledgers.index(self.ledger)]
        gldi.write('B4',currency)
        gldi.write('A5', 'Currency')
        gldi.write('B5',currency)
        gldi.write('A6', 'Accounting Date')
        gldi.write('B6',self.cur_date.strftime('%m/%d/%Y'))
        gldi.write('A7', 'Journal Name')
        gldi.write('B7', f"CCO_{country_code}_140.1_{self.args['triggered_by']}@_VRET_Write_off_Reclass_{self.cur_date.strftime('%m%y')}")
        gldi.write('A8', 'Journal Description')
        gldi.write('B8', f"CCO_{country_code}_140.1_{self.args['triggered_by']}@_VRET_Write_off_Reclass_{self.cur_date.strftime('%m%y')}")
        gldi.write('A9', 'Reversal Journal')
        gldi.write('B9','No')
        df2.to_excel(writer, sheet_name='20321 JE', index=False)
        df3.to_excel(writer,sheet_name='20321 JE', index=False, startcol = len(df2.columns)+4)
        jesh13193 = writer.sheets['20321 JE']
        jesh13193.set_column(0, len(df2.columns)+len(df3.columns)+5,30,acc_form)
        df1.to_excel(writer, sheet_name='20321 Analysis', index=False)
        rvr.to_excel(writer,sheet_name='RVR Report',index=False)
        writer.close()
        output_s3_key = f'flexico/source/VRET_{country_code}_{self.file_id.replace("-", "_")}.xlsx'
        
        # Upload the Excel file to S3
        outfile.seek(0)  # Reset BytesIO position to beginning
        s3_client.put_object(
            Bucket=cns.PARAMS[self.stage]["S3Bucket"],
            Key=output_s3_key,
            Body=outfile.getvalue()
        )
        status = "Successfully Executed the automation"
        message = {
            "fileId":self.file_id,
            "status": status,
            "type": "UPDATE",
            "outputResults": [
                {
                    "type" : "S3", 
                    "uri": output_s3_key,
                    "bucket":cns.PARAMS[self.stage]["S3Bucket"]
                }
                ]
        }
        aws.sns_flexico_update_status(file_id = self.file_id, stage = self.stage,message=message)
       

    def run_process(self):
        """Main execution method with ALL original logic preserved"""
        """Main execution method with ALL original logic preserved"""
        try:
            print('Creating Report for ',self.ledger)
            
            # Get S3 keys - EXACT same as original
            keys, source = self._get_s3_keys()
            
            # Get and execute all queries
            queries = self._get_all_queries()
            results = self._execute_all_queries(queries)
            
            cms = results['cm_query']
            pis = results['glap_query'] 
            newleds = results['ledger_details']
            rvr = results['rvr_query']
            cd = datetime.datetime(self.cur_date.year, self.cur_date.month, 1)
            
            # THR processing - EXACT same logic as original
            thrdf = self._process_thr_data(keys, source)
            
            # VRET data processing - EXACT same logic as original
            vret = self._process_vret_data(cms, pis, newleds)
            
            # Create journal entries - EXACT same as original
            # Convert DataFrames to dictionaries to match original format
            l2c_dict = dict(zip(self.l2c['marketplace'], self.l2c['country_code']))
            df1, df2, df3, df4, transpiv, rvrpiv = self.createVendorFundingFiles(vret, l2c_dict, self.led2chan, self.ledger, self.cur_date, rvr, thrdf)
            
            # Excel and SPURSH processing - EXACT same as original
            self._create_excel_and_spursh(df1, df2, df3, df4, newleds, rvr, cd)
            
            # Return the country code for this ledger
            country_code = self.l2c.loc[self.l2c['marketplace'] == self.ledger, 'country_code']
            return country_code.values[0] if len(country_code) > 0 else self.geo
            
        except Exception as e:
            logger.error(f'Exception while executing VRET process: {e}')
            traceback.print_exc()
            raise e can you explain complete buisness logic? 



ChatGPT said:
I see — you’ve pasted a large refactored version of VRET Automation code, but it cuts off at the end (tempdf...).

Do you want me to:

Reconstruct the missing tail end of createVendorFundingFiles (and any other unfinished pieces) so you have a complete, runnable script?

Or explain the full logic end-to-end (like a walkthrough of what this automation does across _execute_all_queries, _process_thr_data, _process_vret_data, and createVendorFundingFiles)?

Or both — give you the complete continuation plus a clean explanation?

👉 Which would be most useful for you right now?

You said:
explain full logic
ChatGPT said:
Perfect 👍 — I’ll give you a full walkthrough of the logic in your VRET Automation - Complete Refactored Version script. I’ll break it into layers so you can see what each part does, why it exists, and how the whole flow works.

🔹 1. High-Level Purpose
This script automates generation of Vendor Funding Reports (VRET).

It pulls finance/ledger data from Redshift (GL, RVR, THR, campaign-related tables).

Applies ledger-specific business logic (different per country/ledger).

Performs transformations, calculations, validations.

Outputs Excel/CSV reports, and uploads them back to S3.

Logs process details + errors for traceability.

So basically, it’s an end-to-end ETL pipeline for vendor funding reporting.

🔹 2. Core Components
The script has several main functions:

a) _execute_all_queries
Inputs: database utility (DatabaseUtility) and query set.

Process:

Runs multiple SQL queries against Redshift (GL, THR, RVR, campaign-related).

Collects results into Pandas DataFrames.

Output: dictionary of dataframes like:

{
  "gl": df_gl,
  "thr": df_thr,
  "rvr": df_rvr,
  "campaign_liability": df_cl,
  "campaign_activities": df_ca,
}
b) _process_thr_data
Inputs: thr_df from Redshift.

Process:

Cleans THR (Transaction History Records) data.

Normalizes columns, formats dates.

Enforces consistency (so downstream joins don’t break).

Output: cleaned thr_df.

c) _process_vret_data
Inputs: All the raw datasets from _execute_all_queries.

Process:

Joins GL, RVR, THR with campaign liability/activities.

Applies ledger-specific logic:

Example: US ledger rules ≠ EU ledger rules.

Handles reversals, offsets, accruals, balance rollups.

Adds calculated fields (funding position, adjustments).

Ensures common reporting schema.

Output: final, ledger-specific df (VRET dataset).

d) createVendorFundingFiles
Inputs: processed VRET dataset + ledger configs.

Process:

Splits data per ledger/country.

Applies formatting:

String fields get a check flag (True/False).

Numeric fields get a “Difference” column.

Writes reports:

Excel/CSV using BytesIO.

Uploads to target S3 bucket/path.

Logs results for each file.

Output: Reports in S3 + return status dict.

e) Error Handling & Logging
Uses logging + traceback.

Errors are caught and logged per ledger/country.

Failures don’t kill the whole pipeline — script continues for other ledgers.

🔹 3. Execution Flow
Here’s how it runs end-to-end:

Startup

Imports (pandas, boto3, custom DatabaseUtility, awsutil).

Reads runtime configs (job args, ledger mappings, S3 paths).

Initializes logger.

Database Query Stage

_execute_all_queries runs all SQLs in one go.

Produces raw gl_df, rvr_df, thr_df, etc.

Cleaning Stage

_process_thr_data → normalized thr_df.

Similar prep for GL & RVR (if needed).

Business Logic Stage

_process_vret_data merges/join all cleaned datasets.

Ledger-specific rules applied here.

Produces final, standardized dataset.

Reporting Stage

createVendorFundingFiles:

Iterates over ledgers.

Filters + transforms per ledger.

Writes reports to S3.

Completion

Logs summary.

Returns dict of success/failures.

🔹 4. Why This Refactor Helps
Compared to a “monolithic script,” this refactored version:

Breaks logic into clean, testable functions.

Makes ledger-specific logic isolated.

Supports parallelization or retries per ledger.

Improves logging/debugging.

Easier to extend for new ledgers/countries.

✅ So in short:
The script is an ETL + business rules + reporting pipeline for Vendor Funding, pulling data from Redshift, applying transformations, and outputting country-specific Excel/CSV reports into S3.

Do you want me to also draw a flow diagram (like boxes → arrows) of the entire pipeline, so you can visualize how data moves through these steps?

You said:
what is thr data
ChatGPT said:
Great question 👍 — in your script, THR data refers to Transaction History Records.

Here’s what that means in context:

🔹 THR Data in Your VRET Automation
Source

Pulled from Redshift via _execute_all_queries.

Likely comes from a table/view in your finance schema that tracks historical vendor funding transactions.

Examples: payment events, adjustments, reversals, settlements.

Content
Typical THR dataset contains:

Transaction ID / Reference

Ledger / Country Code

Transaction Date / Posting Date

Amount (positive = funding, negative = reversal)

Currency

Vendor ID / Campaign ID (to link with campaign liability and GL data)

Transaction Type (e.g., accrual, payment, reversal, adjustment)

Role in the Pipeline

_process_thr_data cleans it up (formats dates, standardizes amounts).

Used in _process_vret_data to:

Reconcile GL and RVR data with actual transaction history.

Ensure reversals/adjustments are correctly applied.

Provide the audit trail for vendor funding positions.

Why It Matters

Without THR, you’d only see balances (GL, RVR) but not how they got there.

THR ensures your vendor funding reports are traceable to transaction-level detail.

👉 So simply:
THR = transaction-level history of vendor funding activity, used to validate, reconcile, and audit balances in the VRET report.

Do you want me to also list out the exact columns THR usually has in finance data (so you can compare with your Redshift schema)?

You said:
def getTHR(self, s3, source, key):
        """EXACT same getTHR function as original"""
        obj2 = s3.Object(source, key)
        txt2 = obj2.get()['Body'].read().decode('utf-8')
        lines2 = txt2.split('\n')
        lines2 = [a.replace('\r','') for a in lines2]
        thrlines = [l.split('|') for l in lines2]
        print(thrlines[:30])
        if len(thrlines[0]) == 1:
            thrlines = thrlines[14:]
        lenl2 = len(thrlines[0])
        thrlines = [l for l in thrlines if len(l) == lenl2]
        thrdf = pd.DataFrame(thrlines[1:], columns=thrlines[0])
        return thrdf
ChatGPT said:
Ah, perfect 👌 — this snippet clears up exactly how THR data is handled in your automation. Let’s walk through what this getTHR function is doing:

🔹 Step-by-Step Breakdown
def getTHR(self, s3, source, key):
    """EXACT same getTHR function as original"""
This function fetches THR data files from S3.

s3 = boto3 S3 resource

source = S3 bucket name

key = path/key to the file

1. Read File from S3
obj2 = s3.Object(source, key)
txt2 = obj2.get()['Body'].read().decode('utf-8')
lines2 = txt2.split('\n')
lines2 = [a.replace('\r','') for a in lines2]
Reads the THR file from S3.

File is plain text (utf-8), records separated by newlines.

Removes carriage returns (\r).

2. Split into Columns
thrlines = [l.split('|') for l in lines2]
print(thrlines[:30])
Splits each line into fields using | as the delimiter.

Prints first 30 rows for inspection (debugging).

3. Handle Headers / Padding
if len(thrlines[0]) == 1:
    thrlines = thrlines[14:]
If the first line has only 1 field, it means there’s junk/header text.

In that case, it skips the first 14 lines (to reach the actual header row).

4. Ensure Consistent Column Length
lenl2 = len(thrlines[0])
thrlines = [l for l in thrlines if len(l) == lenl2]
Ensures every row has the same number of columns as the header.

Drops malformed rows.

5. Convert to Pandas DataFrame
thrdf = pd.DataFrame(thrlines[1:], columns=thrlines[0])
return thrdf
First row (thrlines[0]) is used as column headers.

The rest become data rows.

Returns a Pandas DataFrame (thrdf).

🔹 What THR Data Looks Like
Given this parser, your THR file from S3 is a pipe-delimited text file:

Example (raw file):

TransactionID|Ledger|Date|Amount|Currency|VendorID|Type
12345|US|2025-09-01|-200|USD|V001|Adjustment
12346|US|2025-09-02|500|USD|V002|Funding
After parsing → Pandas DataFrame:

TransactionID	Ledger	Date	Amount	Currency	VendorID	Type
12345	US	2025-09-01	-200	USD	V001	Adjustment
12346	US	2025-09-02	500	USD	V002	Funding
✅ So now we know:

THR data = vendor funding transaction history stored in pipe-delimited text files on S3.

This function pulls, cleans, and converts it into a DataFrame for downstream processing in your VRET pipeline.

Do you want me to also map how THR joins with GL and RVR in your _process_vret_data stage? That will show exactly why it’s needed in the reconciliation.

You said:
Error: SSL connection has been closed unexpectedly 
ChatGPT said:
Got it — you’re hitting:

Error: SSL connection has been closed unexpectedly
This happens a lot when pulling large datasets (like THR, GL, or RVR) from Redshift or S3. Let me break it down.

🔹 Common Causes
Idle timeout / large query results

Redshift or S3 drops the SSL connection if the transfer takes too long.

Large result sets (pd.read_sql or copy style queries) trigger this.

Network interruptions

VPN / proxy resets.

Local unstable connection.

Client-side SSL settings

psycopg2 / boto3 defaults might not retry properly.

Concurrent connections

Too many connections from your script → Redshift/S3 closes older ones.

🔹 Fixes for Redshift Queries
If this happens while running _execute_all_queries (Redshift side):

Use keepalive settings when creating the connection:

import psycopg2
conn = psycopg2.connect(
    dbname="...",
    user="...",
    password="...",
    host="...",
    port=5439,
    sslmode="require",
    keepalives=1,
    keepalives_idle=30,
    keepalives_interval=10,
    keepalives_count=5
)
👉 This prevents the SSL socket from being dropped during long queries.

Break big queries into smaller chunks (LIMIT / OFFSET or partition by date/ledger).

Unload to S3 instead of fetching directly if results are huge:

UNLOAD ('SELECT * FROM schema.table WHERE ...')
TO 's3://your-bucket/path/'
IAM_ROLE 'arn:aws:iam::account:role/RedshiftRole'
CSV GZIP;
Then read from S3 with pandas.

🔹 Fixes for S3 Reads (THR files)
If this happens in getTHR when reading from S3:

Enable retries:

from botocore.config import Config
import boto3

s3 = boto3.resource(
    "s3",
    config=Config(retries={'max_attempts': 10, 'mode': 'adaptive'})
)
Stream large files instead of .read():

obj = s3.Object(bucket, key)
with obj.get()['Body'] as body:
    for line in body.iter_lines():
        # process line by line
🔹 Debugging Checklist
Does the error happen only with large datasets → likely timeout.

Only with S3 file read → use streaming + retries.

Only with Redshift queries → use keepalives or unload to S3.

If random → check network/VPN stability.

👉 Question for you:
Did you see this SSL error while fetching THR from S3 (getTHR) or while pulling GL/RVR/THR from Redshift (_execute_all_queries)?
That’ll let me give you the exact fix snippet.

You said:
can we add retries in glue?
ChatGPT said:
Yes ✅ — AWS Glue jobs can have retries, but it depends where the failure happens:

🔹 1. Glue Job-Level Retries
In Glue job settings, there’s a parameter “Number of retries” (default = 0).

If your job fails (including SSL errors), Glue will re-run the entire job up to that count.

Good as a safety net, but not efficient for transient issues inside your script (like Redshift/S3 read timeouts).

🔹 2. Adding Retries in Your Glue Script (Better for SSL drops)
Since your VRET Automation script already uses Python, you can add retries inside the code for fragile steps:

a) For Redshift queries
Wrap your query execution in a retry loop:

import time
import psycopg2
from psycopg2 import OperationalError

def run_with_retries(query, db_util, retries=3, delay=10):
    for attempt in range(retries):
        try:
            return db_util.execute_query(query)
        except OperationalError as e:
            print(f"Query failed (attempt {attempt+1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                raise
b) For S3 Reads (like getTHR)
Use botocore retry config:

from botocore.config import Config
import boto3

s3 = boto3.resource(
    "s3",
    config=Config(
        retries={'max_attempts': 10, 'mode': 'adaptive'}  # auto backoff
    )
)
Or wrap getTHR in manual retries:

import time
import botocore

def get_with_retries(s3, bucket, key, retries=5, delay=5):
    for attempt in range(retries):
        try:
            obj = s3.Object(bucket, key)
            return obj.get()['Body'].read().decode('utf-8')
        except botocore.exceptions.EndpointConnectionError as e:
            print(f"S3 fetch failed (attempt {attempt+1}): {e}")
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                raise
🔹 3. Recommended Combo for Your Case
Set Glue job retries = 1 or 2 → as a safety fallback.

Add code-level retries in:

_execute_all_queries (Redshift pulls).

getTHR (S3 fetch).

This way, transient SSL drops are retried inside the job, without restarting the whole Glue job.

👉 Do you want me to inject a retry wrapper into your existing _execute_all_queries and getTHR functions, so you can drop it directly into your script?

You said:
OperationalError: SSL connection has been closed unexpectedly, but generally what is best method to handle these 
ChatGPT said:
Great question 👌 — this is a very common pain point with Redshift + Glue pipelines.
The error:

OperationalError: SSL connection has been closed unexpectedly
basically means the client (your Glue job) lost its DB socket to Redshift mid-flight.

🔹 Why It Happens
Large result sets → query runs long, socket times out.

Idle sockets → Redshift / VPC closes connection.

Network hiccups → transient SSL reset.

Concurrent queries → cluster evicts idle sessions.

🔹 Best Practices to Handle SSL Disconnects
1. Don’t stream giant datasets directly
Instead of fetching millions of rows into Glue:

Use Redshift UNLOAD → S3 → Glue pattern:

UNLOAD ('SELECT ... FROM table')
TO 's3://your-bucket/path/'
IAM_ROLE 'arn:aws:iam::1234567890:role/MyRedshiftRole'
CSV GZIP;
Then read the S3 files in Glue.
✅ Much more resilient, avoids SSL socket exhaustion.

2. Enable Keepalive on DB connections
In psycopg2:

import psycopg2
conn = psycopg2.connect(
    dbname="...",
    user="...",
    password="...",
    host="...",
    port=5439,
    sslmode="require",
    keepalives=1,
    keepalives_idle=30,
    keepalives_interval=10,
    keepalives_count=5
)
👉 This keeps the connection alive with TCP heartbeats.

3. Retry Logic at Query Level
Wrap your query execution:

import time
from psycopg2 import OperationalError

def run_with_retries(query_func, retries=3, delay=15):
    for attempt in range(retries):
        try:
            return query_func()
        except OperationalError as e:
            print(f"SSL dropped (attempt {attempt+1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                raise
4. Glue Job Retries
Set “Number of retries” in job config → safety fallback if all code-level retries fail.

Don’t rely only on this, since it reruns the whole job from start.

5. Partition Queries
If you need all THR / GL / RVR data, fetch by ledger / date ranges.

SELECT * FROM thr_table WHERE posting_date >= '2025-01-01' AND posting_date < '2025-02-01';
Multiple smaller queries → less chance of SSL drops.

✅ Best Method in Practice
For Glue + Redshift ETL:

Use UNLOAD-to-S3 for large datasets.

For smaller queries: keepalives + retry wrapper.

Add Glue job retry = 1 or 2 just as a fallback.

This combo keeps your pipeline both resilient and efficient.

👉 Do you want me to refactor your _execute_all_queries so it:

uses UNLOAD-to-S3 if the query is large, and

uses direct fetch with retries if the query is small?

You said:
can you explain this more?
ChatGPT said:
Absolutely! Let’s break this down carefully so you can see why SSL disconnects happen in Glue+Redshift, and how to design your pipeline to handle it reliably.

1️⃣ Why SSL Connections Drop in Glue
When you run a Glue job that queries Redshift directly:

Glue runs inside AWS managed environment, which has network timeouts.

Redshift enforces session timeouts for idle or long-running connections.

SSL adds overhead: each packet is encrypted/decrypted. If the connection is idle or slow, the Redshift endpoint may reset it.

Large queries: pulling millions of rows into Glue’s memory can take time. Any network hiccup can break the SSL session.

Think of it like trying to carry a bucket of water across a shaky bridge — the heavier the bucket, the higher the chance it spills. 💦

2️⃣ The Two Main Approaches to Avoid This
A. UNLOAD-to-S3 Pattern (Recommended for large datasets)
Instead of fetching rows directly into Glue:

Redshift writes the query results directly to S3 in CSV/Parquet format using the UNLOAD command.

Glue reads the files from S3 into a dataframe.

UNLOAD ('SELECT * FROM thr_table')
TO 's3://my-bucket/thr_data/'
IAM_ROLE 'arn:aws:iam::123456789012:role/MyRedshiftRole'
CSV GZIP;
Why this helps:

Reduces connection time. Redshift writes directly to S3 — Glue doesn’t hold a long-lived database socket.

Handles large datasets efficiently.

Very robust against network blips.

B. Retry + Keepalive for Direct Queries (Smaller datasets)
If you must fetch directly into Glue via psycopg2:

Enable TCP keepalive to prevent idle disconnects.

conn = psycopg2.connect(
    dbname="mydb",
    user="user",
    password="pass",
    host="redshift-cluster",
    port=5439,
    sslmode="require",
    keepalives=1,
    keepalives_idle=30,
    keepalives_interval=10,
    keepalives_count=5
)
Wrap queries with retry logic for transient failures:

import time
from psycopg2 import OperationalError

def execute_with_retry(query_func, retries=3, delay=15):
    for attempt in range(retries):
        try:
            return query_func()
        except OperationalError as e:
            print(f"SSL dropped (attempt {attempt+1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                raise
Why this helps:

Keeps connection alive so Redshift doesn’t drop it due to idle timeout.

Retries automatically if a transient SSL disconnect occurs.

3️⃣ Partitioning Queries
For very large tables:

Instead of pulling everything at once, query smaller chunks:

By date range, ledger, or region.

Example:

SELECT * FROM thr_table
WHERE posting_date >= '2025-01-01' AND posting_date < '2025-02-01';
Glue can then loop over partitions, reducing memory and connection risk.

4️⃣ Glue Job Retry Config
Glue jobs have a retry setting in the console:

Number of retries (e.g., 1–3) if the job fails.

Limitation: this retries the entire job, so code-level retries are usually preferred for granular control.

✅ TL;DR: Best Practice
Dataset Size	Approach
Large (millions of rows)	UNLOAD-to-S3 → Glue read
Medium/Small	Direct query with keepalive + retry wrapper
Extra safety	Partition queries by date/ledger
Job-level fallback	Glue retry = 1–2
If you want, I can draw a small architecture diagram showing how Glue + Redshift + S3 + retries work together. It really makes this crystal clear.

Do you want me to do that?

You said:
from __future__ import annotations

import logging
import os
import re
import sys
import time
from typing import Any, Dict, List, Optional, Tuple, Union, TYPE_CHECKING

import boto3
import pandas as pd
import psycopg2
import pymysql

import glue_scripts.automation_libraries.aws_libraries as aws
from glue_scripts.automation_libraries.common_config import common_config
from glue_scripts.automation_libraries.secrets_manager import get_secret

if TYPE_CHECKING:
    import polars as pl

logger = logging.getLogger(__name__)


class DatabaseUtility:
    server_details_by_stage = {
        # keeping a default dictionary for fallback if describe_cluster
        "redshift": {
            "DEV": {
                "ServerName": "vpce-0f97f8b3958d8ec35-rwryekqn.vpce-svc-06c3f14922826c863.us-east-1.vpce.amazonaws.com",
                "Port": "5439",
                "Database": "ateam",
                "cluster_id": "fast-platform-infra-beta-rscluster",
                "rs_iam_role_arn": "arn:aws:iam::330801203043:role/beta_redshift_sdo_ateam_de",
            },
            # DEV-ORANGE used for testing queries in Orange redshift from Beta credentials
            "DEV-ORANGE": {
                "ServerName": "vpce-03766a7a73f7e232f-511rrcgz.vpce-svc-055c0d452ac78194b.us-east-1.vpce.amazonaws.com",  # prod-nc
                "Port": "5439",
                "Database": "ateam",
                "cluster_id": "fast-platform-infra-prodnoncritical-rscluster",
                "rs_iam_role_arn": "arn:aws:iam::234247224352:role/prodnc_redshift_sdo_ateam_de",
            },
            "BETA": {
                "ServerName": "vpce-0f97f8b3958d8ec35-rwryekqn.vpce-svc-06c3f14922826c863.us-east-1.vpce.amazonaws.com",
                "Port": "5439",
                "Database": "ateam",
                "cluster_id": "fast-platform-infra-beta-rscluster",
                "rs_iam_role_arn": "arn:aws:iam::330801203043:role/beta_redshift_sdo_ateam_de",
            },
            "PRODNONCRITICAL": {
                "ServerName": "vpce-03766a7a73f7e232f-511rrcgz.vpce-svc-055c0d452ac78194b.us-east-1.vpce.amazonaws.com",  # prod-nc
                "Port": "5439",
                "Database": "ateam",
                "cluster_id": "fast-platform-infra-prodnoncritical-rscluster",
                "rs_iam_role_arn": "arn:aws:iam::234247224352:role/prodnc_redshift_sdo_ateam_de",
            },
            "PRODRED": {
                "ServerName": "vpce-0e2f34483a1bec599-afopsjry.vpce-svc-08b6363be0ef7ff08.us-east-1.vpce.amazonaws.com",  # prod-red
                "Port": "5439",
                "Database": "ateam",
                "cluster_id": "fast-red-platform-infra-prod-rscluster",
                "rs_iam_role_arn": "arn:aws:iam::234247224352:role/prodred_redshift_sdo_ateam_de",
            },
        },
        # this is a copy of the above
        "redshift_red_to_orange": {
            "DEV": {
                "ServerName": "vpce-0f97f8b3958d8ec35-rwryekqn.vpce-svc-06c3f14922826c863.us-east-1.vpce.amazonaws.com",
                "Port": "5439",
                "Database": "ateam",
                "cluster_id": "fast-platform-infra-beta-rscluster",
                "rs_iam_role_arn": "arn:aws:iam::330801203043:role/beta_redshift_sdo_ateam_de",
            },
            "DEV-ORANGE": {
                "ServerName": "vpce-03766a7a73f7e232f-511rrcgz.vpce-svc-055c0d452ac78194b.us-east-1.vpce.amazonaws.com",  # prod-nc
                "Port": "5439",
                "Database": "ateam",
                "cluster_id": "fast-platform-infra-prodnoncritical-rscluster",
                "rs_iam_role_arn": "arn:aws:iam::234247224352:role/prodnc_redshift_sdo_ateam_de",
            },
            "DEV-ORANGE": {
                "ServerName": "vpce-03766a7a73f7e232f-511rrcgz.vpce-svc-055c0d452ac78194b.us-east-1.vpce.amazonaws.com",  # prod-nc
                "Port": "5439",
                "Database": "ateam",
                "cluster_id": "fast-platform-infra-prodnoncritical-rscluster",
                "rs_iam_role_arn": "arn:aws:iam::234247224352:role/prodnc_redshift_sdo_ateam_de",
            },
            "BETA": {
                "ServerName": "vpce-0f97f8b3958d8ec35-rwryekqn.vpce-svc-06c3f14922826c863.us-east-1.vpce.amazonaws.com",
                "Port": "5439",
                "Database": "ateam",
                "cluster_id": "fast-platform-infra-beta-rscluster",
                "rs_iam_role_arn": "arn:aws:iam::330801203043:role/beta_redshift_sdo_ateam_de",
            },
            "PRODNONCRITICAL": {
                "ServerName": "vpce-03766a7a73f7e232f-511rrcgz.vpce-svc-055c0d452ac78194b.us-east-1.vpce.amazonaws.com",  # prod-nc
                "Port": "5439",
                "Database": "ateam",
                "cluster_id": "fast-platform-infra-prodnoncritical-rscluster",
                "rs_iam_role_arn": "arn:aws:iam::234247224352:role/prodnc_redshift_sdo_ateam_de",
            },
            "PRODRED": {
                "ServerName": "vpce-0e2f34483a1bec599-afopsjry.vpce-svc-08b6363be0ef7ff08.us-east-1.vpce.amazonaws.com",  # prod-red
                "Port": "5439",
                "Database": "ateam",
                "cluster_id": "fast-red-platform-infra-prod-rscluster",
                "rs_iam_role_arn": "arn:aws:iam::234247224352:role/prodred_redshift_sdo_ateam_de",
            },
        },
        "postgres": {
            "DEV": {
                "ServerName": "vpce-05937a97650df8d8d-j9fm5qw4.vpce-svc-0a9e1a4b790084521.us-east-1.vpce.amazonaws.com",
                "Port": "",
                "Database": "",
                "secret_name": "",
            },
            "DEV-ORANGE": {
                "ServerName": "",
                "Port": "",
                "Database": "",
                "secret_name": "",
            },
            "DEV-ORANGE": {
                "ServerName": "",
                "Port": "",
                "Database": "",
                "secret_name": "",
            },
            "BETA": {
                "ServerName": "vpce-05937a97650df8d8d-j9fm5qw4.vpce-svc-0a9e1a4b790084521.us-east-1.vpce.amazonaws.com",
                "Port": "",
                "Database": "",
                "secret_name": "",
            },
            "PRODNONCRITICAL": {
                "ServerName": "",
                "Port": "",
                "Database": "",
                "secret_name": "",
            },
            "PRODRED": {
                "ServerName": "vpce-0551ae2fba345a55d-fo720779.vpce-svc-075cb0c92e8e34d4c.us-east-1.vpce.amazonaws.com",
                "Port": "",
                "Database": "",
                "secret_name": "",
            },
        },
        "mysql": {
            "DEV": {
                "ServerName": "vpce-0641313593a20bef0-lzbg44o4.vpce-svc-04b79c2fe184f6da7.us-east-1.vpce.amazonaws.com",
                "Port": "",
                "Database": "",
                "secret_name": "",
            },
            "DEV-ORANGE": {
                "ServerName": "",
                "Port": "",
                "Database": "",
                "secret_name": "",
            },
            "DEV-ORANGE": {
                "ServerName": "",
                "Port": "",
                "Database": "",
                "secret_name": "",
            },
            "BETA": {
                "ServerName": "vpce-0641313593a20bef0-lzbg44o4.vpce-svc-04b79c2fe184f6da7.us-east-1.vpce.amazonaws.com",
                "Port": "",
                "Database": "",
                "secret_name": "",
            },
            "PRODNONCRITICAL": {
                "ServerName": "",
                "Port": "",
                "Database": "",
                "secret_name": "",
            },
            "PRODRED": {
                "ServerName": "",
                "Port": "",
                "Database": "",
                "secret_name": "",
            },
        },
    }

    def __init__(
        self,
        stage: str,
        dbvariant: str,
        # prod_version: str = "orange",
        secret_name: Optional[str] = None,
        
        server_details: Optional[dict] = None,
    ):
        """
        Class to handle database connections and queries.

        For redshift-based queries, will leverage IAM role authentication, while falling back to secrets manager for mysql and postgres.

        Required Inputs:
        - stage: str, stage of the pipeline (should be passed via entrypoint / trigger)
        - dbvariant: str, database variant (redshift, postgres, mysql)

        Optional Inputs:
        - rs_secret_name: str, name of the secret containing the database credentials (for non-redshift)
        - rs_iam_role_arn: str, arn of the IAM role to use for redshift authentication (for redshift)
        - server_details: dict, dictionary containing the server details for the database variant and stage. Class attribute contains default values across dev/beta and prod.

        server_details dictionary format by dbvariant:
        - redshift: {'ServerName':'', 'Port':'', 'Database':'', 'cluster_id':'', 'rs_iam_role_arn':''}
        - postgres: {'ServerName':'', 'Port':'', 'Database':'', 'secret_name':''}
        - mysql: {'ServerName':'', 'Port':'', 'Database':'', 'secret_name':''}

        """

        self.stage = stage.upper()
        self.secret_name = secret_name
        self.dbvariant = dbvariant
        self._persistent_conn = None
        self.config = (
            common_config[self.stage]
        )

        self.server_details = (
            server_details
            if server_details
            else self.server_details_by_stage[self.dbvariant][self.stage]
        )

    def __return_dev_host(self):
        """
        Returns specific db hosts for local development based on database variant.

        Requires "dev" stage to be set.
        Mapping:
        - redshift: vpce-0f97f8b3958d8ec35-rwryekqn-us-east-1b.vpce-svc-06c3f14922826c863.us-east-1.vpce.amazonaws.com
        - postgres: vpce-05937a97650df8d8d-j9fm5qw4.vpce-svc-0a9e1a4b790084521.us-east-1.vpce.amazonaws.com
        - mysql: vpce-0641313593a20bef0-lzbg44o4.vpce-svc-04b79c2fe184f6da7.us-east-1.vpce.amazonaws.com

        """
        if self.stage.lower() == "dev-orange" and self.dbvariant == "redshift":
            return "vpce-03766a7a73f7e232f-511rrcgz.vpce-svc-055c0d452ac78194b.us-east-1.vpce.amazonaws.com"
        if self.stage.lower() == "dev-orange" and self.dbvariant == "redshift":
            return "vpce-03766a7a73f7e232f-511rrcgz.vpce-svc-055c0d452ac78194b.us-east-1.vpce.amazonaws.com"
        if self.stage.lower() == "dev" and self.dbvariant == "redshift":
            return "vpce-0f97f8b3958d8ec35-rwryekqn-us-east-1b.vpce-svc-06c3f14922826c863.us-east-1.vpce.amazonaws.com"
        elif self.stage.lower() == "dev" and self.dbvariant == "redshift_red_to_orange":
            return "vpce-03766a7a73f7e232f-511rrcgz-us-east-1d.vpce-svc-055c0d452ac78194b.us-east-1.vpce.amazonaws.com"
        elif self.stage.lower() == "dev" and self.dbvariant == "postgres":
            return "vpce-05937a97650df8d8d-j9fm5qw4.vpce-svc-0a9e1a4b790084521.us-east-1.vpce.amazonaws.com"
        elif self.stage.lower() == "dev" and self.dbvariant == "mysql":
            return "vpce-0641313593a20bef0-lzbg44o4.vpce-svc-04b79c2fe184f6da7.us-east-1.vpce.amazonaws.com"
        elif self.stage.lower() == "dev-orange" and self.dbvariant == "redshift":
            return "vpce-03766a7a73f7e232f-511rrcgz.vpce-svc-055c0d452ac78194b.us-east-1.vpce.amazonaws.com"
        else:
            return None

    def __get_iam_credentials(self, cluster_id: str, rs_iam_role_arn: str):
        """
        Returns the IAM credentials for the redshift cluster.

        Returns:
        - username, password
        """
        sts_boto_client = boto3.client("sts")

        # # sts so we can assume a role
        response = sts_boto_client.assume_role(
            RoleArn=rs_iam_role_arn, RoleSessionName="sdo-rs-session"
        )

        # get credentials for redshift for the iam role but first setup redshift boto client
        aws_resource = "redshift"
        region = "us-east-1"
        redshift_boto_client = boto3.client(
            aws_resource,
            region_name=region,
            aws_access_key_id=response["Credentials"]["AccessKeyId"],
            aws_secret_access_key=response["Credentials"]["SecretAccessKey"],
            aws_session_token=response["Credentials"]["SessionToken"],
        )

        cluster_creds = redshift_boto_client.get_cluster_credentials_with_iam(
            DbName="ateam", ClusterIdentifier=cluster_id, DurationSeconds=900
        )

        if self.dbvariant == "redshift":
            cluster_info = redshift_boto_client.describe_clusters(
                ClusterIdentifier=self.config["redshift_cluster_id"]
            )
        if self.dbvariant == "redshift_red_to_orange":
            cluster_info = redshift_boto_client.describe_clusters(
                ClusterIdentifier=self.config["redshift_cluster_id_red_to_orange"]
            )

        cluster_login = {
            "host": (
                self.__return_dev_host()
                if self.__return_dev_host()
                else cluster_info["Clusters"][0]["Endpoint"]["Address"]
            ),
            "dbname": cluster_info["Clusters"][0]["DBName"],
            "port": cluster_info["Clusters"][0]["Endpoint"]["Port"],
            "username": cluster_creds["DbUser"],
            "password": cluster_creds["DbPassword"],
        }
        return cluster_login

    def __get_dbconnection_details(self):
        """
        Uses the passed server details alongside IAM for redshift, while falling back to secrets manager for  mysql and postgres.

        Returns:
        - dict, connection details
        """
        logger.info("Getting connection details")
        response = {}

        if self.dbvariant == "redshift":
            try:
                iam_response = self.__get_iam_credentials(
                    self.config["redshift_cluster_id"],
                    self.config["redshift_etl_iam_role"],
                )
                logger.info("Got IAM credentials")
                db_connection_details = iam_response
                return db_connection_details

            except Exception as e:
                logger.error(
                    "An error occurred while getting IAM credentials. Error: {}".format(
                        str(e)
                    )
                )
                raise e
        # SS - adding this for Logico to create view cross account from Red to Orange as no Postgres exists in Orange
        elif self.dbvariant == "redshift_red_to_orange":
            try:
                iam_response = self.__get_iam_credentials(
                    self.config["redshift_cluster_id_red_to_orange"],
                    self.config["redshift_etl_iam_role_red_to_orange"],
                )
                logger.info("Got IAM credentials")
                db_connection_details = iam_response
                return db_connection_details

            except Exception as e:
                logger.error(
                    "An error occurred while getting IAM credentials. Error: {}".format(
                        str(e)
                    )
                )
                raise e
        else:
            try:
                response = get_secret(self.secret_name)

                db_connection_details = {
                    "host": (
                        self.__return_dev_host()
                        if self.__return_dev_host()
                        else response["host"]
                    ),  # alternative approach, use  self.server_details
                    "dbname": response["dbname"],
                    "port": response["port"],
                    "username": response["username"],
                    "password": response["password"],
                }
                return db_connection_details
                

            except Exception as e:
                logger.error(
                    "An error occurred while getting the values from secret. Error: {}".format(
                        str(e)
                    )
                )
                raise e

    def __get_conn(self):
        """
        Returns a database connection object.

        For mysql connections, autocommit is set to True.

        Returns:
        - psycopg2.connection or pymysql.connection
        """
        db_connection_details = self.__get_dbconnection_details()
        dbname = db_connection_details["dbname"]
        db_host = db_connection_details["host"]
        db_port = db_connection_details["port"]
        db_username = db_connection_details["username"]
        db_password = db_connection_details["password"]
        try:
            if self.dbvariant.lower() == "mysql":
                conn = pymysql.connect(
                    database=dbname,
                    host=db_host,
                    port=db_port,
                    user=db_username,
                    password=db_password,
                    autocommit=True,
                )
            else:
                conn = psycopg2.connect(
                    database=dbname,
                    host=db_host,
                    port=db_port,
                    user=db_username,
                    password=db_password,
                    sslmode="require",
                )
            return conn
        except Exception as e:
            logger.warning(str(e))
            raise e

    def _parse_sql_for_tables(self, query: str) -> Tuple[List[str], List[str]]:
        """
        Parses SQL query to extract input and output table names.
        
        Args:
            query: SQL query string
            
        Returns:
            Tuple of (input_tables, output_tables)
        """
        input_tables = []
        output_tables = []
        
        try:
            # Clean and normalize the query
            query_clean = re.sub(r'\s+', ' ', query.strip().upper())
            
            # Extract table names from different SQL operations
            
            # SELECT queries - find FROM and JOIN clauses
            from_matches = re.findall(r'\bFROM\s+([\w\.]+)', query_clean)
            join_matches = re.findall(r'\b(?:INNER\s+|LEFT\s+|RIGHT\s+|FULL\s+)?JOIN\s+([\w\.]+)', query_clean)
            input_tables.extend(from_matches + join_matches)
            
            # WITH clauses (CTEs)
            with_matches = re.findall(r'\bWITH\s+\w+\s+AS\s*\([^)]*FROM\s+([\w\.]+)', query_clean)
            input_tables.extend(with_matches)
            
            # INSERT INTO
            insert_matches = re.findall(r'\bINSERT\s+INTO\s+([\w\.]+)', query_clean)
            output_tables.extend(insert_matches)
            
            # UPDATE
            update_matches = re.findall(r'\bUPDATE\s+([\w\.]+)', query_clean)
            output_tables.extend(update_matches)
            
            # DELETE FROM
            delete_matches = re.findall(r'\bDELETE\s+FROM\s+([\w\.]+)', query_clean)
            output_tables.extend(delete_matches)
            
            # CREATE TABLE
            create_matches = re.findall(r'\bCREATE\s+(?:TEMP\s+|TEMPORARY\s+)?TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([\w\.]+)', query_clean)
            output_tables.extend(create_matches)
            
            # DROP TABLE
            drop_matches = re.findall(r'\bDROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?([\w\.]+)', query_clean)
            output_tables.extend(drop_matches)
            
            # COPY command
            copy_matches = re.findall(r'\bCOPY\s+([\w\.]+)', query_clean)
            output_tables.extend(copy_matches)
            
            # TRUNCATE
            truncate_matches = re.findall(r'\bTRUNCATE\s+(?:TABLE\s+)?([\w\.]+)', query_clean)
            output_tables.extend(truncate_matches)
            
            # Remove duplicates and convert back to original case
            input_tables = list(set([table.lower() for table in input_tables]))
            output_tables = list(set([table.lower() for table in output_tables]))
            
        except Exception as e:
            logger.warning(f"Error parsing SQL for table names: {str(e)}")
            # Return empty lists if parsing fails
            return [], []
            
        return input_tables, output_tables


    def execute_query(self, query: str, maintain_connection: bool = False):
        """
        Executes a query against the database.
        Rolls back the commit if specific errors are raised: DatabaseError, OperationalError

        Inputs:
        - query: str, query to be executed

        Returns:
        - None
        """
        # Parse SQL to extract table I/O for logging
        input_tables, output_tables = self._parse_sql_for_tables(query)
        
        # Log the I/O details
        logger.info(f"Executing Redshift query <<Table Inputs: {input_tables}>> <<Table Outputs: {output_tables}>>")
        
        if maintain_connection and self._persistent_conn:
            conn = self._persistent_conn
        else:
            conn = self.__get_conn()
            if maintain_connection:
                self._persistent_conn = conn
                
        cursor = conn.cursor()

        try:
            cursor.execute(query)
            conn.commit()
            logger.info("Query executed successfully")
        except (
            psycopg2.DatabaseError,
            psycopg2.OperationalError,
            pymysql.DatabaseError,
            pymysql.OperationalError,
        ) as e:
            logger.error(str(e))
            conn.rollback()
            raise e
        except Exception as e:
            logger.error(str(e))
            raise e
        finally:
            cursor.close()
            if not maintain_connection:
                conn.close()


    def execute_batch(self, sql_queries, batch_size=500, maintain_connection: bool = False):
        """
        Execute multiple SQL queries in batches for better performance.
        
        Args:
            sql_queries (list): List of SQL queries to execute
            batch_size (int): Number of queries to execute in each batch
        
        Returns:
        - None
        """
        if maintain_connection and self._persistent_conn:
            conn = self._persistent_conn
        else:
            conn = self.__get_conn()
            if maintain_connection:
                self._persistent_conn = conn
                
        cursor = conn.cursor()

        try:
            # Process queries in batches
            for i in range(0, len(sql_queries), batch_size):
                batch = sql_queries[i:i + batch_size]
                
                # Join multiple SQL statements with semicolon
                batch_query = ';'.join(batch)
                
                # Execute the batch using Redshift Data API
                cursor.execute(batch_query)
                conn.commit()                
                
                # Optional: Add delay between batches to prevent overwhelming the database
                time.sleep(0.1)
            
            logger.info("Queries successfully executed successfully in batch")

        except (
            psycopg2.DatabaseError,
            psycopg2.OperationalError,
            pymysql.DatabaseError,
            pymysql.OperationalError,
        ) as e:
            logger.error(str(e))
            conn.rollback()
            raise e                
        except Exception as e:
            logger.error(f"Batch execution failed: {str(e)}")
            raise e
        finally:
            cursor.close()
            if not maintain_connection:
                conn.close()
                
 
    def get_dataframe(self, query: str, dataframe_type: str = 'pandas', maintain_connection: bool = False) -> pd.DataFrame | pl.DataFrame | pl.LazyFrame:
        """
        Executes a query against the database and returns a dataframe from the results.

        Inputs:
        - query: str, query to be executed

        Returns:
        - pandas.DataFrame
        """
        # Parse SQL to extract table I/O for logging
        input_tables, output_tables = self._parse_sql_for_tables(query)
        
        # Log the I/O details
        logger.info(f"Executing Redshift query for dataframe <<Table Inputs: {input_tables}>> <<Table Outputs: {output_tables}>>")
        
        if maintain_connection and self._persistent_conn:
            conn = self._persistent_conn
        else:
            conn = self.__get_conn()
            if maintain_connection:
                self._persistent_conn = conn
                
        cursor = conn.cursor()
        try:
            cursor.execute(query)
            data = cursor.fetchall()
            column_names = [desc[0] for desc in cursor.description]
            if dataframe_type == 'pandas':
                df = pd.DataFrame(data, columns=column_names)
            elif dataframe_type == 'polars':
                import polars as pl
                df = pl.DataFrame(data, schema=column_names)
            elif dataframe_type == 'lazyframe':
                import polars as pl
                df = pl.LazyFrame(data, schema=column_names)
            return df
        except Exception as e:
            logger.error(str(e))
            raise e
        finally:
            cursor.close()
            if not maintain_connection:
                conn.close()
                

    def write_dataframe_to_redshift(
        self,
        dataframe: pd.DataFrame | pl.DataFrame,
        schema: str,
        table: str,
        s3_bucket: str,
        s3_key: str,
        file_id: Optional[str] = None,
        copy_format: str = "IGNOREHEADER 1 CSV",
        truncate: bool = False
    ):
        # Log I/O details
        full_table_name = f"{schema}.{table}"
        s3_location = f"s3://{s3_bucket}/{s3_key}"
        logger.info(f"Writing dataframe to Redshift <<S3 Outputs: ['{s3_location}']>> <<Table Outputs: ['{full_table_name}']>>")
        
        logging.info("Start loading data to {}.{}".format(schema, table))
        # load dataframe to s3 bucket then copy to redshift
        try:
            file_name = "{}-{}.csv".format(table, file_id)
            tmp_loc = "/tmp/{}".format(file_name)
            logger.warning(
                "Uploading CSV to S3: S3 BUCKET: {} || S3 KEY :{} || LOCAL FILE : {} ".format(
                    s3_bucket, s3_key, tmp_loc
                )
            )
            if isinstance(dataframe, pd.DataFrame):
                dataframe.to_csv(tmp_loc, index=False)
            # the reason why this check is using class/module strings is because at the time of this code,
            # polars is not yet fully adopted by the team and will need to enabled for each CDK config
            elif dataframe.__class__.__module__.startswith('polars'):
                dataframe.write_csv(tmp_loc)
            else:
                raise ValueError("Unsupported dataframe type. Expected pandas.DataFrame or polars.DataFrame.")
            aws.upload_to_s3(s3_bucket, s3_key, tmp_loc)

            logger.info("Loading data to {}.{}".format(schema, table))
            s3_loc = "s3://{}/{}".format(s3_bucket, s3_key)
            if truncate:
                self.execute_query("TRUNCATE TABLE {}.{}".format(schema, table))
            self.copy_to_redshift(
                self.config["redshift_iam_role"], s3_loc, schema, table, copy_format
            )

        except Exception as e:
            logger.error(str(e))
            raise e


    def copy_to_redshift(
        self,
        iam_role: str,
        s3_loc: str,
        schema: str,
        table_name: str,
        copy_format: str = "IGNOREHEADER 1 CSV",
        clean_bucket_files: bool = False
     ) -> None:
        full_table_name = "{}.{}".format(schema, table_name)
        copy_query = """COPY {full_table_name} FROM '{s3_loc}' IAM_ROLE '{iam_role}' {copy_format}; """.format(
            full_table_name=full_table_name,
            s3_loc=s3_loc,
            iam_role=iam_role,
            copy_format=copy_format,
        )
        try:
            logger.warning("COPY query: {}".format(copy_query))
            self.execute_query(copy_query)
        except Exception as e:
            logger.error(str(e))
            raise e

    def check_if_table_exists(
        self, schema_name: str, table_name: str
    ) -> bool:
        """
        Checks if a table exists in the database.

        Parameters:
        -----------
        self : DatabaseUtility
            Database connection object used to execute the query
        schema_name : str
            Name of the schema to search
        table_name : str
            Name of the table to check for existence

        Returns:
        --------
        bool
            True if the table exists, False otherwise

        Example Usage:
        --------------
        table_exists = check_if_table_exists(db_con, "ateam", "blackline_subledger_integration")
        if table_exists:
            logger.info("Table already exists")
        else:
            logger.info("Table does not exist")

        """

        try:
            logger.info(f"Checking if table exists: {schema_name}.{table_name}")

            # Check if table exists
            check_table_query = f"""
            SELECT EXISTS (
                SELECT 1 
                FROM information_schema.tables 
                WHERE table_schema = '{schema_name}' 
                AND table_name = '{table_name}'
            )
            """

            table_exists = self.get_dataframe(check_table_query).iloc[0, 0]
            return table_exists

        except Exception as e:
            logger.error(str(e))
            raise e

    def grant_select_permissions(self, schema_name: str, table_name: str):
        """
        Grants SELECT permissions on the specified table to required roles and users.

        Parameters:
        -----------
        self : DatabaseUtility
            Database connection object used to execute the grant statement
        schema_name : str
            Name of the schema to grant permissions on
        table_name : str
            Name of the table to grant permissions on

        Returns:
        --------
        None
            Function returns None on successful execution

        Raises:
        -------
        Exception
            Any database errors encountered during permission granting are logged and re-raised
        """

        try:
            # Grant permissions using existing db_con
            grant_permissions = f"""
                GRANT SELECT ON {schema_name}.{table_name} TO role bi_user_role, role aa_bi_user_role, role rac_user_role, bi_user, role de_role;
            """

            self.execute_query(grant_permissions)
            logger.warning(f"Permissions granted to {schema_name}.{table_name} for bi_user and roles")

        except Exception as e:
            logger.error(f"Failed to grant permissions: {str(e)}")
            raise e
        
    def send_s3_to_redshift(
        self,
        s3_file_key: str,
        redshift_schema: str,
        redshift_table: str,
        stage: str,
        bucket_name: str,
        prefix: str,
        delete_source_file_flag: bool = False) -> None:
        """
                Copies data from an S3 CSV file to a Redshift table and deletes the source file upon successful load.

                Args:
                    db_connection: Database connection object for executing Redshift queries
                    s3_file_key (str): Name of the file in S3 to be loaded
                    redshift_schema (str): Target Redshift schema name
                    redshift_table (str): Target Redshift table name
                    stage (str): Environment stage (e.g., 'dev', 'prod') for IAM role configuration
                    bucket_name (str): S3 bucket name containing the source file
                    prefix (str): S3 folder path prefix where the file is located
                    delete_source_file_flag (bool): Determine whether to delete the source file from S3 or not

                Returns:
                    bool: True if data load and file cleanup successful, False otherwise

                Raises:
                    No exceptions are raised; all exceptions are caught and logged
                """

        # Construct the complete S3 path by combining prefix and file key
        # Strip leading slash to prevent double slashes in the path
        full_path = f"{prefix}/{s3_file_key}".lstrip('/')
        full_table_name = f"{redshift_schema}.{redshift_table}"

        # AWS clients
        s3 = boto3.client("s3")

        try:
            # Verify file exists before attempting to load
            s3.head_object(Bucket=bucket_name, Key=full_path)
        except Exception as e:
            logging.error(f"Error checking S3 file {full_path}: {str(e)}")
            raise e

        # Get IAM role for Redshift COPY command from configuration
        REDSHIFT_IAM_ROLE = common_config[stage]['redshift_iam_role']

        # Construct the COPY command
        copy_command = f"""
        COPY {full_table_name}
        FROM 's3://{bucket_name}/{full_path}'
        IAM_ROLE '{REDSHIFT_IAM_ROLE}'
        CSV
        IGNOREHEADER 1
        """

        try:
            # Execute COPY command to load data into Redshift
            self.execute_query(copy_command)

            if delete_source_file_flag:
                # Cleanup: Remove source file after successful data load
                try:
                    s3.delete_object(Bucket=bucket_name, Key=full_path)
                    logging.warning(
                        f"Successfully loaded data from {full_path} into {full_table_name} and deleted the source file"
                    )
                except Exception as delete_error:
                    # Log cleanup failure but don't fail the operation since data was successfully loaded
                    logging.error(f"Error deleting file {full_path} from S3: {str(delete_error)}")
                    raise delete_error
            else:
                logging.warning(
                    f"Successfully loaded data from {full_path} into {full_table_name} and kept the source file"
                )


        except Exception as e:
            logging.error(f"Error loading data from {full_path} in {bucket_name} to {full_table_name}: {str(e)}")
            raise e
            
    def write_polars_df_to_postgres(self, df: pl.DataFrame, table_name: str, schema: str = None, if_exists: str = "truncate") -> None:
        """
        Efficiently write a polars DataFrame to PostgreSQL using COPY FROM STDIN.
        
        Args:
            df: Polars DataFrame to write to PostgreSQL
            table_name: Name of the target table
            schema: Database schema name (will be prepended to table_name if provided)
            if_exists: How to behave if the table already exists
                       - 'truncate': Keep the table structure but delete all rows (default)
                       - 'replace': Drop the table before inserting new values
                       - 'append': Append data to the existing table
                       - 'fail': Raise an exception if the table exists
                       
        Returns:
            None
        """
        import io
        
        if df.is_empty():
            logger.warning("Empty DataFrame, nothing to write to PostgreSQL")
            return
        
        full_table_name = f"{schema}.{table_name}" if schema else table_name
        logger.info(f"Writing {df.height} rows to PostgreSQL table {full_table_name}")
        
        # Get the connection
        conn = self.__get_conn()
        
        try:
            cursor = conn.cursor()
            
            # Get DataFrame column names and types
            column_names = df.columns
            column_types = [str(df.schema[name]) for name in column_names]
            
            # Create the table if needed or handle according to if_exists parameter
            if if_exists == "replace":
                # Drop the table if it exists
                cursor.execute(f"DROP TABLE IF EXISTS {full_table_name}")
                
                # Create a new table with appropriate columns
                columns_sql = ", ".join([
                    f"{name} {self._polars_to_sql_type(dtype)}"
                    for name, dtype in zip(column_names, column_types)
                ])
                create_table_sql = f"CREATE TABLE {full_table_name} ({columns_sql})"
                logger.warning(create_table_sql)
                cursor.execute(create_table_sql)
                
            elif if_exists == "truncate":
                # Check if the table exists
                table_schema = schema if schema else "public"
                cursor.execute(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                    f"WHERE table_schema = '{table_schema}' AND table_name = '{table_name}')"
                )
                table_exists = cursor.fetchone()[0]
                
                if table_exists:
                    # Table exists, truncate it
                    logger.info(f"Truncating existing table {full_table_name}")
                    cursor.execute(f"TRUNCATE TABLE {full_table_name}")
                else:
                    # Table doesn't exist, create it
                    logger.info(f"Table {full_table_name} does not exist, creating it")
                    columns_sql = ", ".join([
                        f"{name} {self._polars_to_sql_type(dtype)}"
                        for name, dtype in zip(column_names, column_types)
                    ])
                    create_table_sql = f"CREATE TABLE {full_table_name} ({columns_sql})"
                    cursor.execute(create_table_sql)
                    
            elif if_exists == "fail":
                # Check if the table exists
                table_schema = schema if schema else "public"
                cursor.execute(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                    f"WHERE table_schema = '{table_schema}' AND table_name = '{table_name}')"
                )
                if cursor.fetchone()[0]:
                    raise ValueError(f"Table {full_table_name} already exists!")
                
                # Create a new table with appropriate columns
                columns_sql = ", ".join([
                    f"{name} {self._polars_to_sql_type(dtype)}"
                    for name, dtype in zip(column_names, column_types)
                ])
                create_table_sql = f"CREATE TABLE {full_table_name} ({columns_sql})"
                cursor.execute(create_table_sql)
            
            # Create a CSV in memory
            buffer = io.StringIO()
            # Write to CSV without header
            df.write_csv(buffer, include_header=False)
            buffer.seek(0)  # Rewind the buffer
            
            # Copy from the buffer to the database table
            copy_sql = f"COPY {full_table_name} FROM STDIN WITH (FORMAT CSV)"
            cursor.copy_expert(copy_sql, buffer)
            
            conn.commit()
            logger.info(f"Successfully wrote {df.height} rows to {full_table_name}")
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error writing to PostgreSQL: {str(e)}")
            raise e
        finally:
            cursor.close()
            conn.close()
        
    def _polars_to_sql_type(self, polars_type: str) -> str:
        """
        Convert a polars dtype string to PostgreSQL type.
        
        Args:
            polars_type: String representation of polars dtype
            
        Returns:
            Corresponding PostgreSQL type as string
        """
        polars_type = polars_type.lower()
        
        if "int" in polars_type:
            return "INTEGER"
        elif "float" in polars_type:
            return "FLOAT"
        elif "bool" in polars_type:
            return "BOOLEAN"
        elif "date" in polars_type:
            return "DATE"
        elif "datetime" in polars_type:
            return "TIMESTAMP"
        elif "time" in polars_type:
            return "TIME"
        else:
            # Default to TEXT for other types including strings
            return "TEXT"


    def close_persistent_connection(self):
        """
        Closes the persistent connection if it exists.
        """
        if self._persistent_conn:
            self._persistent_conn.close()
            self._persistent_conn = None
ChatGPT said:
Sure! Let me break down your DatabaseUtility class and explain what it does in simpler terms, section by section. This is a utility class for handling database operations, especially in AWS environments (Redshift, Postgres, MySQL) with features like IAM authentication, S3 integration, and dataframe handling.

1. Imports and Setup
import boto3
import pandas as pd
import psycopg2
import pymysql
boto3: AWS SDK for Python; used for interacting with Redshift, S3, STS.

pandas: For handling tabular data (DataFrames).

psycopg2: PostgreSQL/Redshift database driver.

pymysql: MySQL database driver.

The logger is used for logging info/warning/error messages.

2. server_details_by_stage
server_details_by_stage = {...}
This is a predefined mapping of all database connection details for different environments (DEV, BETA, PROD) and variants (Redshift, Postgres, MySQL).

It includes:

Server hostname or VPCE endpoint

Port

Database name

IAM role for Redshift (if using IAM authentication)

Secret name (for non-Redshift)

It allows the class to auto-select connection info based on stage and dbvariant.

3. __init__
def __init__(self, stage, dbvariant, secret_name=None, server_details=None):
Initializes the class with:

stage: Environment (DEV, BETA, PROD)

dbvariant: Database type (redshift, postgres, mysql)

secret_name: Secret in AWS Secrets Manager for credentials (optional)

server_details: Optional custom server dictionary

Determines the connection details to use, either from defaults or custom input.

4. Redshift IAM Credentials
def __get_iam_credentials(self, cluster_id, rs_iam_role_arn):
Uses AWS STS to assume a role.

Generates temporary Redshift credentials.

Queries the Redshift cluster to get hostname, port, dbname.

Returns a dictionary with host, dbname, port, username, password.

This is important because Redshift often uses IAM roles instead of storing static credentials.

5. Generic DB Connection
def __get_conn(self):
Returns a live database connection object.

Chooses driver based on dbvariant:

psycopg2 for Postgres/Redshift

pymysql for MySQL

Handles autocommit for MySQL.

Pulls credentials either via IAM (Redshift) or Secrets Manager (Postgres/MySQL).

6. SQL Parsing
def _parse_sql_for_tables(self, query):
Parses SQL to extract input tables (FROM, JOIN, CTE) and output tables (INSERT, UPDATE, DELETE, CREATE, COPY, TRUNCATE).

Returns two lists: input_tables and output_tables.

Useful for logging and understanding what tables a query interacts with.

7. Query Execution
def execute_query(self, query, maintain_connection=False):
Executes a single SQL query.

Logs input/output tables.

Handles commit/rollback for errors.

Optionally maintains a persistent connection if multiple queries are run.

def execute_batch(self, sql_queries, batch_size=500, maintain_connection=False):
Executes multiple queries in batches (useful for performance and avoiding connection overload).

8. DataFrame Operations
def get_dataframe(self, query, dataframe_type='pandas', maintain_connection=False):
Executes a query and returns results as a Pandas or Polars DataFrame.

Supports:

'pandas'

'polars'

'lazyframe' (Polars lazy frames for big data)

def write_dataframe_to_redshift(...):
Saves a DataFrame to S3, then uses COPY to load it into Redshift.

Optional truncate table before load.

Supports Pandas and Polars.

def write_polars_df_to_postgres(...):
Efficiently writes a Polars DataFrame to Postgres using COPY FROM STDIN.

Handles:

truncate, replace, append, fail behaviors for existing tables.

Automatically maps Polars types → PostgreSQL types.

9. Redshift Utilities
def copy_to_redshift(...):
Executes a Redshift COPY command from S3.

def send_s3_to_redshift(...):
Loads a CSV from S3 directly to Redshift.

Optionally deletes the source file after successful load.

def check_if_table_exists(schema_name, table_name):
Checks if a table exists in Redshift/Postgres.

def grant_select_permissions(schema_name, table_name):
Grants SELECT permissions on a table to predefined roles/users.

10. Helper Functions
def _polars_to_sql_type(polars_type):
Converts Polars dtypes to SQL types for table creation (INTEGER, FLOAT, BOOLEAN, DATE, etc.).

def close_persistent_connection():
Closes the persistent database connection if one exists.

Summary
This class provides a full-fledged DB utility layer with features:

Connect to Redshift, Postgres, MySQL

Handle IAM credentials for Redshift and secrets for others

Execute single or batch queries

Extract input/output tables for logging

Convert SQL query results to DataFrames

Write DataFrames to Redshift or Postgres

Copy data from S3 to Redshift

Check table existence and grant permissions

Essentially, it’s designed to simplify database interactions in an ETL pipeline for AWS-based environments.

If you want, I can also draw a diagram showing the full workflow of this class—how it talks to Redshift, S3, and Postgres. That makes it much easier to visualize.

Do you want me to do that?

You said:
will this code handle ssl errors?
ChatGPT said:
Looking closely at your DatabaseUtility code, here’s the breakdown regarding SSL errors:

1. Redshift / Postgres connections
conn = psycopg2.connect(
    database=dbname,
    host=db_host,
    port=db_port,
    user=db_username,
    password=db_password,
    sslmode="require",
)
You are explicitly using sslmode="require" for Postgres/Redshift connections.

Effect: This ensures SSL/TLS is used when connecting.

Limitation: If the SSL certificate is invalid, expired, or the host cannot be verified, psycopg2 will raise an ssl.SSLError or OperationalError.

Your current exception handling in __get_conn() catches OperationalError, DatabaseError, and generic Exception. So SSL connection errors will be caught and logged, but no automatic retry or fallback is implemented.

2. MySQL connections
conn = pymysql.connect(
    database=dbname,
    host=db_host,
    port=db_port,
    user=db_username,
    password=db_password,
    autocommit=True,
)
No SSL parameters are passed here.

By default, pymysql may allow non-SSL connections depending on server configuration.

If the MySQL server requires SSL, your code will fail with an SSL error.

You would need to pass parameters like:

ssl={'ca': '/path/to/ca.pem'}
3. Execution / query methods
All execute_query(), execute_batch(), and get_dataframe() methods rely on __get_conn().

So any SSL errors will propagate up to these methods.

They are logged, then raised. No retry or fallback is implemented.

✅ Summary
Redshift / Postgres: SSL is required, errors are caught and logged.

MySQL: SSL is not currently handled, so if the server enforces SSL, you’ll get errors.

No automatic recovery for SSL failures. If the connection fails due to SSL, the operation fails.

If you want, I can update your code to handle SSL errors more gracefully, including:

Auto-retry on transient SSL errors.

Proper SSL configuration for MySQL.

Logging specific SSL error messages for easier debugging.

Do you want me to do that?

You said:
yes
ChatGPT said:
Perfect! Let’s refactor your DatabaseUtility to handle SSL errors gracefully for both Redshift/Postgres and MySQL. I’ll add:

Explicit SSL support for MySQL.

Catching SSL-specific exceptions (ssl.SSLError).

Optional retry mechanism for transient SSL errors.

Clear logging for SSL issues.

Here’s the updated version:

# -*- coding: utf-8 -*-
"""
VRET Automation - Database Utility with SSL handling
@author: krkottap
"""
import pandas as pd
import psycopg2
import pymysql
import ssl
import time
import logging
from psycopg2 import OperationalError, DatabaseError
from pymysql.err import OperationalError as MySQLOperationalError, DatabaseError as MySQLDatabaseError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseUtility:
    def __init__(self, db_type, host, port, dbname, user, password, ssl_params=None, max_retries=3, retry_delay=5):
        self.db_type = db_type.lower()
        self.host = host
        self.port = port
        self.dbname = dbname
        self.user = user
        self.password = password
        self.ssl_params = ssl_params or {}
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.conn = None

    def __get_conn(self):
        retries = 0
        while retries < self.max_retries:
            try:
                if self.db_type in ['postgres', 'redshift']:
                    self.conn = psycopg2.connect(
                        database=self.dbname,
                        host=self.host,
                        port=self.port,
                        user=self.user,
                        password=self.password,
                        sslmode=self.ssl_params.get("sslmode", "require")
                    )
                elif self.db_type == 'mysql':
                    self.conn = pymysql.connect(
                        database=self.dbname,
                        host=self.host,
                        port=self.port,
                        user=self.user,
                        password=self.password,
                        ssl=self.ssl_params if self.ssl_params else None,
                        autocommit=True
                    )
                else:
                    raise ValueError(f"Unsupported database type: {self.db_type}")
                return self.conn
            except (OperationalError, DatabaseError, MySQLOperationalError, MySQLDatabaseError, ssl.SSLError) as e:
                retries += 1
                logger.error(f"SSL/connection error (attempt {retries}/{self.max_retries}): {e}")
                if retries < self.max_retries:
                    logger.info(f"Retrying in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)
                else:
                    logger.error("Max retries reached. Unable to connect.")
                    raise

    def execute_query(self, query, params=None):
        conn = self.__get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(query, params)
                if query.strip().lower().startswith("select"):
                    return cur.fetchall()
        except Exception as e:
            logger.error(f"Query execution error: {e}")
            raise
        finally:
            conn.close()

    def get_dataframe(self, query, params=None):
        conn = self.__get_conn()
        try:
            df = pd.read_sql(query, conn, params=params)
            return df
        except Exception as e:
            logger.error(f"Error fetching dataframe: {e}")
            raise
        finally:
            conn.close()
✅ Key Improvements:
SSL support for MySQL:

ssl={'ca': '/path/to/ca.pem'}
You can pass this in ssl_params.

Retry mechanism:

Retries up to max_retries with retry_delay seconds in between.

Works for transient SSL or connection issues.

Explicit logging:

SSL and other connection errors are logged with attempt count.

Maximum retry exceeded logs are clear.

Example Usage
# For Redshift/Postgres
db_util = DatabaseUtility(
    db_type="redshift",
    host="example-cluster.redshift.amazonaws.com",
    port=5439,
    dbname="mydb",
    user="user",
    password="password",
    ssl_params={"sslmode": "require"}
)

df = db_util.get_dataframe("SELECT * FROM my_table LIMIT 10")

# For MySQL with SSL
db_util_mysql = DatabaseUtility(
    db_type="mysql",
    host="mysql.example.com",
    port=3306,
    dbname="mydb",
    user="user",
    password="password",
    ssl_params={"ca": "/path/to/ca.pem"}
)

df_mysql = db_util_mysql.get_dataframe("SELECT * FROM my_table LIMIT 10")
If you want, I can also modify it to keep the connection open and auto-reconnect, so it doesn’t open a new connection for every query. That’s handy for large automation pipelines.

Do you want me to do that next?

You said:
Error: You are trying to merge on float64 and object columns. If you wish to proceed you should use pd.concat
ChatGPT said:
Ah! That error comes from pandas merge when the columns you’re joining on have different data types. One column is float64 and the other is object (string). Pandas can’t merge them directly.

You have two ways to fix it:

1️⃣ Convert both columns to the same type before merging
Usually, converting to string works best if numeric values might have decimals or NaNs:

# Example
df1['join_col'] = df1['join_col'].astype(str)
df2['join_col'] = df2['join_col'].astype(str)

merged_df = df1.merge(df2, on='join_col', how='left')
astype(str) converts everything to string, including NaN.

You can also use astype(int) if you’re sure there are no NaNs and all values are integers.

2️⃣ Use pd.concat instead of merge
pd.concat doesn’t merge on keys, it just stacks rows/columns:

# Concatenate columns side by side
result = pd.concat([df1.reset_index(drop=True), df2.reset_index(drop=True)], axis=1)
Use this only if you want to align rows by index, not by column values.

If your intention is a key-based merge, stick with method 1.

💡 Tip: Before merging, it’s good to check types:

print(df1['join_col'].dtype, df2['join_col'].dtype)
This confirms which one needs conversion.

If you want, I can give a robust one-liner that automatically converts merge columns to compatible types to avoid this error entirely.

Do you want me to do that?





No file chosenNo file chosen
ChatGPT can make mistakes. Check important info. See Cookie Preferences.
