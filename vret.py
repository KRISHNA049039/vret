def createVendorFundingFiles(self, df, l2c, led2chan, ledger, cd, rvrfilt, thr):
        """createVendorFundingFiles function with memory optimization"""
        print(f"Input DataFrame shape: {df.shape}")
        
        # Handle empty DataFrames
        if df.empty:
            print("Warning: Input DataFrame is empty")
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
        
        df = df.fillna('')
        
        # Handle empty RVR filter
        if rvrfilt.empty:
            print("Warning: RVR filter DataFrame is empty")
            rvrfilt = pd.DataFrame(columns=['RETURN ID', 'TOT BASE REFUND AMT'])
        else:
            rvrfilt['RETURN ID'] = rvrfilt['RETURN ID'].astype(str)
        
        df.columns = ['LEDGER','PERIOD','CO','LOC','CC','ACCT','PROD','CHAN','PROJ','JOURNAL NAME','CURRENCY_CODE','TRANSACTION AMOUNT','VENDOR_NAME','TRANSACTION NUM','CATEGORY']
        print('ORIG DF LENGTH: ', len(df))
        
        # Optimize groupby operation
        df = df.groupby(by=['LEDGER','PERIOD','CO','LOC','CC','ACCT','PROD','CHAN','PROJ','JOURNAL NAME','CURRENCY_CODE','VENDOR_NAME','TRANSACTION NUM','CATEGORY'])['TRANSACTION AMOUNT'].sum().reset_index()
        df['TRANSACTION AMOUNT'] = pd.to_numeric(df['TRANSACTION AMOUNT'], errors='coerce').fillna(0)
        df['TRANSACTION NUM'] = df['TRANSACTION NUM'].astype(str)
        print('DF LENGTH: ', len(df))
        
        # Get country code safely
        country_code_result = self.l2c.loc[self.l2c['marketplace'] == ledger, 'country_code']
        ln = country_code_result.values[0] if len(country_code_result) > 0 else self.geo
        
        if ln in ['PL','UK','FR','DE','ES','IT','CZ','EG','AE'] and not thr.empty:
            print(f"THR DataFrame shape: {thr.shape}")
            print(list(thr.columns))
            
            # Check if required columns exist
            if 'Transaction Number' in thr.columns and 'Agreement Type' in thr.columns:
                thr['Transaction Number'] = thr['Transaction Number'].astype(str)
                thr['Agreement Type'] = thr['Agreement Type'].fillna('').astype(str)
                maps = thr[['Transaction Number','Agreement Type']].copy()
                maps.columns = ['TRANSACTION NUM','RETURN ID']
                maps = maps.drop_duplicates().reset_index(drop=True)
                
                vret = df.merge(maps, on='TRANSACTION NUM', how='left').fillna('')
                
                if not rvrfilt.empty and 'TOT BASE REFUND AMT' in rvrfilt.columns:
                    rvrjoin = rvrfilt[['RETURN ID','TOT BASE REFUND AMT']].copy()
                    rvrjoin.columns = ['RETURN ID','RVR AMT']
                    rvrjoin['RVR AMT'] = pd.to_numeric(rvrjoin['RVR AMT'], errors='coerce').fillna(0)
                    newrvr = rvrjoin.groupby(by=['RETURN ID'])['RVR AMT'].sum().reset_index()
                    tempfull = vret.merge(newrvr, on='RETURN ID', how='left').fillna(0).reset_index(drop=True)
                    
                    norvr = tempfull[tempfull['RVR AMT']==0].reset_index(drop=True)
                    yesrvr = tempfull[tempfull['RVR AMT']!=0].reset_index(drop=True)
                    
                    newrvrrows = []
                    for s in yesrvr['RETURN ID'].unique():
                        temprvr = yesrvr[yesrvr['RETURN ID']==s].reset_index(drop=True)
                        if len(temprvr)==1:
                            newrvrrows.append(list(temprvr.loc[0]))
                        else:
                            temprvr = temprvr.sort_values(by='TRANSACTION AMOUNT', ascending=False).reset_index(drop=True)
                            newrvrrows.append(list(temprvr.loc[0]))
                            temp2rvr = temprvr[1:].reset_index(drop=True)
                            temp2rvr['RVR AMT'] = 0
                            newrvrrows.extend(temp2rvr.values.tolist())
                    
                    if newrvrrows:
                        yesrvrdf2 = pd.DataFrame(newrvrrows, columns=list(norvr.columns))
                        full = pd.concat([norvr, yesrvrdf2]).reset_index(drop=True)
                    else:
                        full = norvr.copy()
                else:
                    full = vret.copy()
                    full['RVR AMT'] = 0
            else:
                print("Warning: Required THR columns not found, proceeding without THR mapping")
                full = df.copy()
                full['RETURN ID'] = ''
                full['RVR AMT'] = 0
        else:
            if not rvrfilt.empty and 'TOT BASE REFUND AMT' in rvrfilt.columns:
                rvrjoin = rvrfilt[['RETURN ID','TOT BASE REFUND AMT']].copy()
                rvrjoin.columns = ['RETURN ID','RVR AMT']
                rvrjoin['RVR AMT'] = pd.to_numeric(rvrjoin['RVR AMT'], errors='coerce').fillna(0)
                newrvr = rvrjoin.groupby(by='RETURN ID')['RVR AMT'].sum().reset_index()
                
                df['TRANSACTION NUM'] = df['TRANSACTION NUM'].fillna('')
                df['RETURN ID'] = df['TRANSACTION NUM'].apply(lambda x: x.split('_')[0] if '_' in str(x) else '')
                df['RETURN ID'] = df['RETURN ID'].astype(str)
                newrvr['RETURN ID'] = newrvr['RETURN ID'].astype(str)
                full = df.merge(newrvr, on='RETURN ID', how='left').fillna(0).reset_index(drop=True)
            else:
                full = df.copy()
                full['RETURN ID'] = ''
                full['RVR AMT'] = 0
        
        ta, rvra = list(full['TRANSACTION AMOUNT']), list(full['RVR AMT'])
        full['RVR AMT'] = [min(ta[i],rvra[i]) if rvra[i]!=0 else rvra[i] for i in range(len(full))]
        full['Final Amount'] = full['TRANSACTION AMOUNT'] - full['RVR AMT']
        
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
        country_code = self._get_country_code(ledger)
        tempdf['CO']=['6L' if country_code=='EU' else str(a) for a in tempdf['CO']]
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
        tempdf['CH2']=[ch1[i] if ch1[i]!='0000' else led2chan.get(country_code, '0000') for i in range(len(tempdf))]
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
        
        return tempdf, je1df, je2df, fullje2,transpiv2,rvrpiv2     can you explain complete logic
