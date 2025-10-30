Option Compare Database


Dim HoldSelect As Integer
Dim CurrentTree As String
Dim Keep As Boolean

Private Sub btnClosePreview_Click()
    listTree.Visible = False
    listPreview.Visible = False
    Me.listRule.SetFocus
    btnClosePreview.Visible = False
End Sub

Private Sub btnDeleteRule_Click()
    Dim TypeSelect As String
    Dim ValueSelect As String
    Dim DLSelect As Integer
    Dim sqlDeleteRule As String
    Dim EMP_IDSelect As String
    If Me.listRule.ListIndex <> -1 Then
        TypeSelect = Me.listRule.Column(1, Me.listRule.ListIndex)
        ValueSelect = Me.listRule.Column(2, Me.listRule.ListIndex)
        DLSelect = Me.listRule.Column(3, Me.listRule.ListIndex)
        EMP_IDSelect = Me.listRule.Column(4, Me.listRule.ListIndex)
        
        Select Case TypeSelect
                Case "Location"
                    sqlDeleteRule = "DELETE FROM dbo_DL_RULE_LOC WHERE DLID=" & DLSelect & " AND E_Location='" & ValueSelect & "'"
                Case "TREE"
                    sqlDeleteRule = "DELETE FROM dbo_PS_DL_RULE_TREE WHERE DLID=" & DLSelect & " AND EMP_NAME='" & ValueSelect & "'"
                Case "User"
                    sqlDeleteRule = "DELETE FROM dbo_PS_DL_RULE_USER WHERE DLID=" & DLSelect & " AND EMP_NAME='" & ValueSelect & "'"
        End Select
    Else
        MsgBox ("No rule selected.")
        Exit Sub
    End If
    
    DoCmd.SetWarnings False
    DoCmd.RunSQL (sqlDeleteRule)
    DoCmd.SetWarnings True
    
    
    
    If listTree.Visible = True Then
        Keep = True
        Call btnShowTree_Click
    End If

    If listPreview.Visible = True Then
        Call btnPreview_Click
    End If
    
    Call RefreshList
End Sub

Private Sub btnPreview_Click()
    listPreview.Visible = True
    listTree.Visible = False
    btnClosePreview.Visible = True
    
     
     Dim db As DAO.Database
     Dim qdf As DAO.QueryDef
     Dim rs As DAO.Recordset
     Set db = CurrentDb
     Set qdf = db.CreateQueryDef("")
     qdf.Connect = "ODBC;Driver={SQL Server};Server=HOU-SQLOP-P1;Database=DListDB;" 'UID=DListAdmin;PWD=D1str0L1st443;"
     qdf.SQL = "EXEC LIST_PREVIEW @DLID=" & cboList.Column(1)
     

     Set rs = qdf.OpenRecordset(dbOpenForwardOnly, dbReadOnly)
     Me.listPreview.RowSource = ""
     
     Do While Not rs.EOF
        Me.listPreview.AddItem rs![EmployeeName]
        rs.MoveNext
    Loop
    
    rs.Close
    Set rs = Nothing
    Set qdf = Nothing
    Set db = Nothing
End Sub

Private Sub btnShowTree_Click()
    Dim ValueSelect As String
    Dim TypeSelect As String
    Dim FlagSelect As String
    FlagSelect = Me.listRule.Column(0, Me.listRule.ListIndex)
    TypeSelect = Me.listRule.Column(1, Me.listRule.ListIndex)
    
    If Keep = False Then
        ValueSelect = Me.listRule.Column(2, Me.listRule.ListIndex)
        CurrentTree = Me.listRule.Column(2, Me.listRule.ListIndex)
    Else
        ValueSelect = CurrentTree
    End If
    
    DLSelect = Me.listRule.Column(3, Me.listRule.ListIndex)

     Dim db As DAO.Database
     Dim qdf As DAO.QueryDef
     Dim rs As DAO.Recordset
    listPreview.Visible = False
    listTree.Visible = True
    btnClosePreview.Visible = True
     Set db = CurrentDb
     Set qdf = db.CreateQueryDef("")
     qdf.Connect = "ODBC;Driver={SQL Server};Server=HOU-SQLOP-P1;Database=DListDB;UID=DListAdmin;PWD=D1str0L1st443;"
     qdf.SQL = "EXEC TREE_PREVIEW @MANAGER='" & ValueSelect & "', @DLID=" & DLSelect & ";"
     
     'qdf.Parameters(0).Value = "'Lisa Kuderick'"
     'qdf.Parameters(1).Value = 1
     Set rs = qdf.OpenRecordset(dbOpenForwardOnly, dbReadOnly)
     Me.listTree.RowSource = ""

     Do While Not rs.EOF
        Me.listTree.AddItem rs![EmployeeName]
        rs.MoveNext
    Loop
    
    rs.Close
    Set rs = Nothing
    Set qdf = Nothing
    Set db = Nothing
    'MsgBox (Me.listRule.ListIndex) 'Here
    
    Keep = False
    'MsgBox (CurrentTree)
End Sub

Private Sub cboList_AfterUpdate()
    Call RefreshList
End Sub

Private Sub cboRule_AfterUpdate()
    If (cboRule.Value = "User") Or (cboRule.Value = "TREE") Then
      Me.lblData.Caption = "Name"
      cboData.RowSource = "SELECT EmployeeName, EmployeeID FROM dbo_Employee_List"
      cboData.Value = ""
    End If
    If (cboRule.Value = "Location") Then
      Me.lblData.Caption = "Location"
      cboData.RowSource = "SELECT DISTINCT E_Location FROM dbo_Employee_List"
      cboData.Value = ""
    End If
End Sub


Private Sub Command5_Click()
    'Dim conn As Object
    'Set conn = CreateObject("ADODB.Connection")
    'Dim rsEmployee As Object
    'Set rsEmployee = CreateObject("ADODB.Recordset")
    'Dim rsRule_Loc As Object
    'Set rsRule_Loc = CreateObject("ADODB.Recordset")
    'Dim sqlInsert As String
    'conn.ConnectionString = "Provider=SQLOLEDB;Data Source=CORPOPERATIONS;Initial Catalog=DListDB;USER ID=DListAdmin;Password=;Trusted_Connection=No"
    
    'conn.Open
    'DoCmd.SetWarnings False
    'rsEmployee.Open "SELECT * FROM Employee_List", conn
    'conn.Close
    'DoCmd.RunSQL ("DELETE FROM Employee")
    'Do While Not rsEmployee.EOF
    '    sqlInsert = "INSERT INTO Employee (EmployeeID, EmployeeName, FirstName, LastName, JobTitle, HireDate, Location, SupervisoryOrg, Manager, M_EmployeeNumber, Status, InactiveDate, Username, Email) VALUES (" & rsEmployee("EmployeeID").Value & ",'" & rsEmployee("EmployeeName").Value & "','" & rsEmployee("FirstName").Value & "','" & rsEmployee("LastName").Value & "','" & rsEmployee("JobTitle").Value & "','" & rsEmployee("HireDate").Value & "','" & rsEmployee("E_Location").Value & "','" & rsEmployee("SupervisoryOrg").Value & "','" & rsEmployee("Manager").Value & "','" & rsEmployee("M_EmployeeID").Value & "','" & rsEmployee("E_Status").Value & "','" & rsEmployee("InactiveDate").Value & "','" & rsEmployee("Username").Value & "','" & rsEmployee("Email").Value & "')"
     '   'MsgBox (sqlInsert)
    '    DoCmd.RunSQL (sqlInsert)
    '    'MsgBox (rsEmployee("EmployeeID").Value)
    '    rsEmployee.MoveNext
    'Loop
    
    'DoCmd.SetWarnings True
End Sub

Private Sub btnAddRule_Click()
    Dim sqlAddRule As String
    If cboRule.Value = "" Then
        MsgBox ("No Rule Selected")
        Exit Sub
    End If
    
    If cboData.Value = "" Then
        MsgBox ("No Value Selected")
        Exit Sub
    End If
    
    Select Case cboRule.Value
        Case "Location"
            sqlAddRule = "INSERT INTO dbo_DL_RULE_LOC VALUES(" & cboList.Column(1) & ",'" & cboData.Value & "','" & cboInclude.Value & "')"
        Case "Tree"
            sqlAddRule = "INSERT INTO dbo_PS_DL_RULE_TREE VALUES(" & cboList.Column(1) & ",'" & cboData.Value & "','" & cboInclude.Value & "')"
        Case "User"
            sqlAddRule = "INSERT INTO dbo_PS_DL_RULE_USER VALUES(" & cboList.Column(1) & ",'" & cboData.Value & "','" & cboInclude.Value & "')"
        Case Else
            MsgBox ("Invalid Rule")
            Exit Sub
    End Select
    DoCmd.SetWarnings False
    DoCmd.RunSQL (sqlAddRule)
    DoCmd.SetWarnings True
    HoldSelect = Me.listRule.ListIndex
    Call RefreshList
    Me!listRule.Selected(HoldSelect + 1) = True
    Call listRule_AfterUpdate
    'MsgBox (Me.listRule.ListIndex) 'Here
    If listTree.Visible = True Then
        Keep = True
        Call btnShowTree_Click
    End If
    If listPreview.Visible = True Then
        Call btnPreview_Click
    End If
End Sub

Private Sub Command17_Click()
    MsgBox (cboList.Column(1))
End Sub

Private Sub Command20_Click()
    Call Shell("\\cabotog.com\cogroot\corporate\prod\Procount\Distribution Lists\RunListUpload.bat")
End Sub

Private Sub btnRefresh_Click()

Dim response As VbMsgBoxResult


    response = MsgBox("This will refresh the database to reflect any changes in active Directory. The process will take about 30 seconds. Do you want to continue?", vbYesNo + vbQuestion, "Confirmation")
    If response = vbYes Then
        'Dim db As DAO.Database
        'Dim qdf As DAO.QueryDef
        'Set db = CurrentDb
        'Set qdf = db.CreateQueryDef("")
        
        'qdf.Connect = "ODBC;Driver={SQL Server};Server=HOU-SQLOP-P1;Database=DListDB;" 'UID=DListAdmin;PWD=D1str0L1st443;"
        'qdf.SQL = "EXEC msdb.dbo.sp_start_job N'Refresh Employees From Ad'"
        'qdf.ReturnsRecords = False
        'qdf.Execute dbFailOnError
        
        'Set qdf = Nothing
        'Set db = Nothing
        
        Call Shell("\\cabotog.com\cogroot\corporate\prod\Procount\Distribution Lists\RunADRefresh.bat")
    End If
    
End Sub

Private Sub Form_Load()
    Call RefreshList
    Keep = False
End Sub

Private Function RefreshList()
    listRule.RowSource = "SELECT TYPE_FLAG,'Location' as Rule, E_Location as Data, DLID, '' as EmployeeID FROM dbo_DL_RULE_LOC WHERE DLID = " & cboList.Column(1) & " UNION SELECT TYPE_FLAG, 'Tree' as Rule, dbo_Employee_List.EmployeeName as Data,  dbo_PS_DL_RULE_TREE.DLID, dbo_Employee_List.EmployeeID FROM dbo_PS_DL_RULE_TREE INNER JOIN dbo_Employee_List ON dbo_PS_DL_RULE_TREE.EMP_NAME = dbo_Employee_List.EmployeeName WHERE dbo_PS_DL_RULE_TREE.DLID = " & cboList.Column(1) & " UNION SELECT TYPE_FLAG, 'User' as Rule, dbo_Employee_List.EmployeeName as Data,  dbo_PS_DL_RULE_USER.DLID, dbo_Employee_List.EmployeeID FROM dbo_PS_DL_RULE_USER INNER JOIN dbo_Employee_List ON dbo_PS_DL_RULE_USER.EMP_NAME = dbo_Employee_List.EmployeeName WHERE dbo_PS_DL_RULE_USER.DLID=" & cboList.Column(1)
End Function

Private Sub listPreview_AfterUpdate()
    Dim ValueSelect As String
    ValueSelect = Me.listPreview.Column(0, Me.listPreview.ListIndex)
    cboInclude.Value = "Exclude"
    cboRule.Value = "User"
    cboData = ValueSelect
End Sub

Private Sub listRule_AfterUpdate()
    Dim ValueSelect As String
    Dim TypeSelect As String
    Dim FlagSelect As String
    FlagSelect = Me.listRule.Column(0, Me.listRule.ListIndex)
    TypeSelect = Me.listRule.Column(1, Me.listRule.ListIndex)
    ValueSelect = Me.listRule.Column(2, Me.listRule.ListIndex)
    DLSelect = Me.listRule.Column(3, Me.listRule.ListIndex)
    If Me.listRule.ListIndex <> -1 Then
        If TypeSelect <> "Tree" Or FlagSelect <> "Include" Then
            btnShowTree.Visible = False

            'listPreview.Visible = False
            'MsgBox (Me.listRule.ListIndex) 'Here
            Exit Sub
        End If
    Else
       btnShowTree.Visible = False

       'listPreview.Visible = False
       'MsgBox (Me.listRule.ListIndex) 'Here
       Exit Sub
    End If
    
    btnShowTree.Visible = True

End Sub

Private Sub listTree_AfterUpdate()
    Dim ValueSelect As String
    ValueSelect = Me.listTree.Column(0, Me.listTree.ListIndex)
    
    cboInclude.Value = "Exclude"
    cboRule.Value = "User"
    cboData = ValueSelect
    
    
End Sub
