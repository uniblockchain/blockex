import { Component, OnInit } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { DataService } from '../services';
import { Router} from '@angular/router';
import { Page } from "tns-core-modules/ui/page";
import { RouterExtensions } from "nativescript-angular/router";

@Component({
  selector: 'app-block-details-tns',
  templateUrl: './block-details.component.tns.html',
  styleUrls: ['./block-details.component.tns.css']
})
export class BlockDetailsComponentTns implements OnInit {

  block: any;
  loading_block: boolean = false;
  notFound: boolean = false;

  displayedColumns: any = {
    kernels: ['fee', 'excess', 'id'],
    inputs: ['commitment', 'maturity'],
    outputs: ['commitment', 'maturity', 'coinbase'],
    block: ['name', 'value']
  };

  constructor(
      private router: Router,
      private dataService: DataService,
      private route: ActivatedRoute,
      private pageTns: Page,
      private routerExtensions: RouterExtensions) { }

  goBack() {
      this.routerExtensions.backToPreviousPage();
  }

  ngOnInit() {
     //this.pageTns.actionBarHidden = true;
    this.loading_block = true;
    this.block = {
      header: '',
      data: []
    };
    this.route.params.subscribe( (params) => {
      this.dataService.loadBlock(params.hash).subscribe((blockItem) => {
        this.block.header = 'Block ' + blockItem.height;
        this.block.data = [
          {name: 'Fee', role: 'Block', value: blockItem.fee, additional: blockItem.fee !== 0 ? 'Groth' : ''},
          {name: 'Hash', role: 'Block', value: blockItem.hash, additional: ''},
          {name: 'Difficulty', role: 'Block', value: blockItem.difficulty.toLocaleString(), additional: ''},
          {name: 'Subsidy', role: 'Block', value: blockItem.subsidy.toLocaleString(), additional: 'Groth'},
          {name: 'Chainwork', role: 'Block', value: blockItem.chainwork, additional: ''},
          {name: 'Age', role: 'Block', value: new Date(blockItem.timestamp).toLocaleDateString("en-US", {
            year: 'numeric', month: 'long',
            day: 'numeric', hour: 'numeric',
            minute: 'numeric', second: 'numeric' }), additional: ''}
        ];

        this.block.data = this.block.data.concat(blockItem.inputs.map((item) => {
          item['role'] = "Inputs";
          return item;
        }));
        this.block.data = this.block.data.concat(blockItem.outputs.map((item) => {
          item['role'] = "Outputs";
          return item;
        }));
        this.block.data = this.block.data.concat(blockItem.kernels.map((item) => {
          item['role'] = "Kernels";
          return item;
        }));
      });
      this.loading_block = false;
    });
  }

  public templateSelector(item: any) {
    return item.role;
  }
}